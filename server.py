import asyncio
import json
import os
import websockets

rooms = {}
rooms_lock = asyncio.Lock()

MAX_NAME_LENGTH = 24
MAX_ROOM_LENGTH = 32

def clean_name(name):
    if not isinstance(name, str):
        return "Người chơi"
    name = " ".join(name.strip().split())
    return name[:MAX_NAME_LENGTH] if name else "Người chơi"

def clean_room(room):
    if room is None:
        return ""
    room = str(room).strip()
    return room[:MAX_ROOM_LENGTH] if room else ""

async def send_json(websocket, data):
    try:
        await websocket.send(json.dumps(data, ensure_ascii=False))
        return True
    except (websockets.exceptions.ConnectionClosed, ConnectionError, OSError):
        return False

async def remove_player(room_id, websocket):
    async with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            return
        player = next((p for p in room if p["ws"] is websocket), None)
        if player is None:
            return
        room.remove(player)
        task = player.get("turn_task")
        if task and not task.done():
            task.cancel()
        remaining = list(room)
        if not remaining:
            del rooms[room_id]
    for opp in remaining:
        await send_json(opp["ws"], {
            "type": "disconnect",
            "msg": "Đối thủ đã thoát hoặc mất mạng.",
        })

async def handler(websocket):
    room_id = None
    player = None
    try:
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=15)
        except asyncio.TimeoutError:
            await send_json(websocket, {"type": "error", "msg": "Hết thời gian kết nối phòng."})
            return

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await send_json(websocket, {"type": "error", "msg": "Dữ liệu kết nối không hợp lệ."})
            return

        if data.get("action") != "join":
            await send_json(websocket, {"type": "error", "msg": "Yêu cầu kết nối không hợp lệ."})
            return

        room_id = clean_room(data.get("room"))
        player_name = clean_name(data.get("name"))
        try:
            client_time_limit = int(data.get("time_limit", 0))
        except (ValueError, TypeError):
            client_time_limit = 0

        if not room_id:
            await send_json(websocket, {"type": "error", "msg": "Mã phòng không được để trống."})
            return

        player = {
            "ws": websocket,
            "name": player_name,
            "symbol": None,
            "turn_task": None,
            "time_limit": client_time_limit,
        }

        start_messages = []
        turn_start_messages = []
        waiting_message = None

        async with rooms_lock:
            room = rooms.setdefault(room_id, [])
            if len(room) >= 2:
                await send_json(websocket, {"type": "error", "msg": "Phòng đã đầy! Vui lòng chọn mã khác."})
                return

            room.append(player)

            if len(room) == 1:
                waiting_message = {
                    "type": "waiting",
                    "room": room_id,
                    "player_name": player_name,
                    "msg": "Đã vào phòng. Đang chờ đối thủ...",
                }
            else:
                # 2 người
                player_x, player_o = room[0], room[1]
                player_x["symbol"] = "X"
                player_o["symbol"] = "O"
                room[0]["turn_symbol"] = "X"
                turn_limit = player_x.get("time_limit", 0)
                room[0]["turn_time_limit"] = turn_limit

                old_task = room[0].get("turn_task")
                if old_task and not old_task.done():
                    old_task.cancel()
                room[0]["turn_task"] = None

                start_messages = [
                    (player_x["ws"], {
                        "type": "start",
                        "symbol": "X",
                        "player_name": player_x["name"],
                        "opponent_name": player_o["name"],
                        "room": room_id,
                    }),
                    (player_o["ws"], {
                        "type": "start",
                        "symbol": "O",
                        "player_name": player_o["name"],
                        "opponent_name": player_x["name"],
                        "room": room_id,
                    }),
                ]
                turn_start_messages = [
                    (p["ws"], {"type": "turn_start", "symbol": "X", "seconds": turn_limit})
                    for p in room
                ]

        if waiting_message:
            await send_json(websocket, waiting_message)
        for ws, msg in start_messages:
            await send_json(ws, msg)
        for ws, msg in turn_start_messages:
            await send_json(ws, msg)

        # ==================== RELAY ====================
        async for message in websocket:
            try:
                payload = json.loads(message)
            except (json.JSONDecodeError, TypeError):
                continue

            async with rooms_lock:
                room = rooms.get(room_id)
                if not room:
                    break
                sender = next((p for p in room if p["ws"] is websocket), None)
                if not sender:
                    break

                clients = [p for p in room if p["ws"] is not websocket]
                turn_limit = room[0].get("turn_time_limit", 0)
                outgoing = []
                turn_start = []
                msg_type = payload.get("type")

                if msg_type == "move":
                    r, c = payload.get("r"), payload.get("c")
                    if not isinstance(r, int) or not isinstance(c, int):
                        continue
                    if not (0 <= r < 20 and 0 <= c < 20):
                        continue

                    room_turn = room[0].get("turn_symbol")
                    if room_turn and sender.get("symbol") != room_turn:
                        continue

                    room[0]["turn_symbol"] = "O" if sender.get("symbol") == "X" else "X"
                    next_symbol = room[0]["turn_symbol"]

                    old_task = room[0].get("turn_task")
                    if old_task and not old_task.done():
                        old_task.cancel()
                    room[0]["turn_task"] = None

                    outgoing = [(p["ws"], message) for p in clients]
                    turn_start = [
                        (p["ws"], {"type": "turn_start", "symbol": next_symbol, "seconds": turn_limit})
                        for p in room
                    ]

                elif msg_type == "update_time_limit":
                    try:
                        new_limit = int(payload.get("time_limit", 0))
                    except (ValueError, TypeError):
                        new_limit = 0
                    room[0]["turn_time_limit"] = new_limit
                    outgoing = [(p["ws"], message) for p in clients]

                elif msg_type == "rematch":
                    old_task = room[0].get("turn_task")
                    if old_task and not old_task.done():
                        old_task.cancel()
                    room[0]["turn_task"] = None

                    # Flip symbol
                    for p in room:
                        p["symbol"] = "O" if p["symbol"] == "X" else "X"
                    room[0]["turn_symbol"] = "X"

                    outgoing = [(p["ws"], message) for p in clients]
                    turn_start = [
                        (p["ws"], {"type": "turn_start", "symbol": "X", "seconds": room[0].get("turn_time_limit", 0)})
                        for p in room
                    ]

                elif msg_type == "timeout":
                    loser_sym = payload.get("loser")
                    room[0]["turn_symbol"] = None
                    old_task = room[0].get("turn_task")
                    if old_task and not old_task.done():
                        old_task.cancel()
                    room[0]["turn_task"] = None
                    for p in room:
                        await send_json(p["ws"], {"type": "timeout", "loser": loser_sym})
                    continue

                else:
                    outgoing = [(p["ws"], message) for p in clients]

            for client, msg in outgoing:
                await send_json(client, msg)
            for client, msg in turn_start:
                await send_json(client, msg)

            # Timeout task
            if msg_type == "move" and turn_limit > 0:
                next_symbol = None
                async with rooms_lock:
                    current = rooms.get(room_id)
                    if current:
                        next_symbol = current[0].get("turn_symbol")

                if next_symbol:
                    async def timeout_task(expected, limit):
                        try:
                            await asyncio.sleep(limit)
                            async with rooms_lock:
                                current = rooms.get(room_id)
                                if not current or current[0].get("turn_symbol") != expected:
                                    return
                                current[0]["turn_symbol"] = None
                                recipients = list(current)
                            for p in recipients:
                                await send_json(p["ws"], {"type": "timeout", "loser": expected})
                        except asyncio.CancelledError:
                            return

                    async with rooms_lock:
                        current = rooms.get(room_id)
                        if current:
                            current[0]["turn_task"] = asyncio.create_task(
                                timeout_task(next_symbol, turn_limit)
                            )

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[SERVER ERROR] room={room_id}: {e}")
    finally:
        if room_id and player is not None:
            await remove_player(room_id, websocket)

async def main():
    port = int(os.environ.get("PORT", 3000))
    print("=" * 55)
    print("        CARO ONLINE WEBSOCKET SERVER (VØID FIXED)")
    print("=" * 55)
    print(f"Port: {port} | Max 2 players/room")
    print("=" * 55)
    async with websockets.serve(
        handler, "0.0.0.0", port,
        ping_interval=20, ping_timeout=20, close_timeout=5, max_size=1*1024*1024
    ):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")