import asyncio
import json
import os
import websockets

# ============================================================
# CARO ONLINE WEBSOCKET SERVER
# ============================================================
# Client gửi:
#   {"action": "join", "room": "1234", "name": "Tùng"}
# ============================================================

rooms = {}
rooms_lock = asyncio.Lock()

MAX_NAME_LENGTH = 24
MAX_ROOM_LENGTH = 32
TURN_TIME_LIMIT = 35

def clean_name(name):
    """Làm sạch tên người chơi."""
    if not isinstance(name, str):
        return "Người chơi"

    name = " ".join(name.strip().split())

    if not name:
        return "Người chơi"

    return name[:MAX_NAME_LENGTH]


def clean_room(room):
    """Làm sạch mã phòng."""
    if room is None:
        return ""

    room = str(room).strip()

    if not room:
        return ""

    return room[:MAX_ROOM_LENGTH]


async def send_json(websocket, data):
    """Gửi JSON an toàn."""
    try:
        await websocket.send(
            json.dumps(data, ensure_ascii=False)
        )
        return True
    except (
        websockets.exceptions.ConnectionClosed,
        ConnectionError,
        OSError,
    ):
        return False


async def relay_message(websocket, message):
    """Gửi nguyên message game cho đối thủ."""
    try:
        await websocket.send(message)
        return True
    except (
        websockets.exceptions.ConnectionClosed,
        ConnectionError,
        OSError,
    ):
        return False


async def remove_player(room_id, websocket):
    """Xóa người chơi và báo cho đối thủ."""
    async with rooms_lock:
        room = rooms.get(room_id)

        if not room:
            return

        player = next(
            (p for p in room if p["ws"] is websocket),
            None,
        )

        if player is None:
            return

        room.remove(player)
        task = player.get("turn_task")
        if task and not task.done():
            task.cancel()
        remaining_players = list(room)

        if not remaining_players:
            del rooms[room_id]

    for opponent in remaining_players:
        await send_json(opponent["ws"], {
            "type": "disconnect",
            "msg": "Đối thủ đã thoát hoặc mất mạng.",
        })


async def handler(websocket):
    room_id = None
    player = None

    try:
        try:
            raw_message = await asyncio.wait_for(
                websocket.recv(),
                timeout=15,
            )
        except asyncio.TimeoutError:
            await send_json(websocket, {
                "type": "error",
                "msg": "Hết thời gian kết nối phòng.",
            })
            return

        try:
            data = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            await send_json(websocket, {
                "type": "error",
                "msg": "Dữ liệu kết nối không hợp lệ.",
            })
            return

        if data.get("action") != "join":
            await send_json(websocket, {
                "type": "error",
                "msg": "Yêu cầu kết nối không hợp lệ.",
            })
            return

        room_id = clean_room(data.get("room"))
        player_name = clean_name(data.get("name"))
        
        # === NHẬN THÊM CẤU HÌNH THỜI GIAN TỪ CLIENT ===
        try:
            client_time_limit = int(data.get("time_limit", 35))
        except (ValueError, TypeError):
            client_time_limit = 35
        # ===============================================

        if not room_id:
            await send_json(websocket, {
                "type": "error",
                "msg": "Mã phòng không được để trống.",
            })
            return

        player = {
            "ws": websocket,
            "name": player_name,
            "symbol": None,
            "turn_task": None,
            "turn_symbol": None,
            "time_limit": client_time_limit, # Lưu thời gian của người tạo phòng
        }

        start_messages = []
        opponent_joined_messages = []
        turn_start_messages = []
        waiting_message = None

        async with rooms_lock:
            room = rooms.setdefault(room_id, [])

            if len(room) >= 2:
                await send_json(websocket, {
                    "type": "error",
                    "msg": "Phòng đã đầy! Vui lòng chọn mã khác.",
                })
                return

            room.append(player)

            if len(room) == 1:
                waiting_message = {
                    "type": "waiting",
                    "room": room_id,
                    "player_name": player_name,
                    "msg": "Đã vào phòng. Đang chờ đối thủ...",
                }

            elif len(room) == 2:
                player_x = room[0]
                player_o = room[1]

                player_x["symbol"] = "X"
                player_o["symbol"] = "O"
                room[0]["turn_symbol"] = "X"  
                
                # Lưu time_limit của người tạo phòng (player_x) làm quy chuẩn cho cả phòng
                room[0]["turn_time_limit"] = player_x.get("time_limit", 35)

                opponent_joined_messages = [
                    (
                        player_x["ws"],
                        {
                            "type": "opponent_joined",
                            "opponent_name": player_o["name"],
                        },
                    ),
                    (
                        player_o["ws"],
                        {
                            "type": "opponent_joined",
                            "opponent_name": player_x["name"],
                        },
                    ),
                ]

                start_messages = [
                    (
                        player_x["ws"],
                        {
                            "type": "start",
                            "symbol": "X",
                            "player_name": player_x["name"],
                            "opponent_name": player_o["name"],
                            "room": room_id,
                        },
                    ),
                    (
                        player_o["ws"],
                        {
                            "type": "start",
                            "symbol": "O",
                            "player_name": player_o["name"],
                            "opponent_name": player_x["name"],
                            "room": room_id,
                        },
                    ),
                ]

                turn_start_messages = [
                    (p["ws"], {
                        "type": "turn_start",
                        "symbol": "X",
                        "seconds": TURN_TIME_LIMIT,
                    }) for p in room
                ]

        if waiting_message:
            await send_json(websocket, waiting_message)

        for ws, message in opponent_joined_messages:
            await send_json(ws, message)

        for ws, message in start_messages:
            await send_json(ws, message)
        for ws, message in turn_start_messages:
            await send_json(ws, message)

        # --------------------------------------------------------
        # Relay dữ liệu Caro (Chỉ bắt đầu tính giờ từ nước đi đầu tiên)
        # --------------------------------------------------------
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
                if sender is None:
                    break

                clients = [p for p in room if p["ws"] is not websocket]

                if payload.get("type") == "move":
                    room_turn = room[0].get("turn_symbol") if room else None
                    if room_turn and sender.get("symbol") != room_turn:
                        continue

                    room[0]["turn_symbol"] = "O" if sender.get("symbol") == "X" else "X"
                    next_symbol = room[0]["turn_symbol"]
                    
                    # Hủy timer cũ nếu có
                    old_task = room[0].get("turn_task")
                    if old_task and not old_task.done():
                        old_task.cancel()
                    room[0]["turn_task"] = None

                    outgoing = [(p["ws"], message) for p in clients]
                    turn_start = [(p["ws"], {
                        "type": "turn_start",
                        "symbol": next_symbol,
                        "seconds": TURN_TIME_LIMIT,
                    }) for p in room]
                elif payload.get("type") == "rematch":
                    outgoing = [(p["ws"], message) for p in clients]
                    turn_start = []
                else:
                    outgoing = [(p["ws"], message) for p in clients]
                    turn_start = []

            for client, outgoing_message in outgoing:
                await relay_message(client, outgoing_message)
            for client, timer_message in turn_start:
                await send_json(client, timer_message)

            # Tạo timer đếm ngược nếu phòng có bật giới hạn thời gian (turn_limit > 0)
            turn_limit = current_room[0].get("turn_time_limit", 35)
            # Tạo timer đếm ngược nếu phòng có bật giới hạn thời gian (turn_limit > 0)
            turn_limit = room[0].get("turn_time_limit", 35)
            if payload.get("type") == "move" and room_id and turn_limit > 0:
                async def timeout_task(expected_symbol):
                    try:
                        await asyncio.sleep(turn_limit)
                        async with rooms_lock:
                            current_room = rooms.get(room_id)
                            if not current_room or current_room[0].get("turn_symbol") != expected_symbol:
                                return
                            current_room[0]["turn_symbol"] = None
                            recipients = list(current_room)
                        for p in recipients:
                            await send_json(p["ws"], {
                                "type": "timeout",
                                "loser": expected_symbol,
                                "seconds": 0,
                            })
                    except asyncio.CancelledError:
                        return

                async with rooms_lock:
                    current_room = rooms.get(room_id)
                    if current_room:
                        current_room[0]["turn_task"] = asyncio.create_task(timeout_task(next_symbol))

    except websockets.exceptions.ConnectionClosed:
        pass

    except asyncio.CancelledError:
        raise

    except Exception as e:
        print(f"[SERVER ERROR] room={room_id}: {e}")

    finally:
        if room_id and player is not None:
            await remove_player(room_id, websocket)


async def main():
    port = int(os.environ.get("PORT", 3000))

    print("=" * 55)
    print("        CARO ONLINE WEBSOCKET SERVER")
    print("=" * 55)
    print(f"Server đang chạy tại port: {port}")
    print("Mỗi phòng tối đa: 2 người")
    print("=" * 55)

    async with websockets.serve(
        handler,
        "0.0.0.0",
        port,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=5,
        max_size=1 * 1024 * 1024,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer đã dừng.")