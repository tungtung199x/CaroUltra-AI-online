import asyncio
import json
import os
import time
import websockets

rooms = {}
rooms_lock = asyncio.Lock()

# Thời gian mỗi lượt cố định (giây) — phải khớp client
TURN_SECS = 35


def clean(text, max_len=24, default=""):
    if not isinstance(text, str):
        return default
    text = " ".join(text.strip().split())
    return text[:max_len] if text else default


async def send(ws, data):
    try:
        await ws.send(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass


async def remove_player(room_id, ws):
    async with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            return

        player = next((p for p in room if p["ws"] is ws), None)
        if not player:
            return

        room.remove(player)

        remaining = list(room)
        if not remaining:
            del rooms[room_id]
            return

        # Hủy timeout nếu còn
        if remaining[0].get("task") and not remaining[0]["task"].done():
            try:
                remaining[0]["task"].cancel()
            except Exception:
                pass

    for p in remaining:
        await send(p["ws"], {"type": "disconnect", "msg": "Đối thủ đã thoát."})


async def start_timeout(room_id, expected_turn, turn_secs):
    """Timeout theo đồng hồ server — chính xác TURN_SECS giây"""
    try:
        await asyncio.sleep(turn_secs)
        async with rooms_lock:
            room = rooms.get(room_id)
            if not room or len(room) < 2:
                return
            if room[0].get("turn") == expected_turn:
                room[0]["turn"] = None
                room[0]["turn_deadline"] = None
                for p in room:
                    await send(p["ws"], {
                        "type": "timeout",
                        "loser": expected_turn,
                        "server_ts": time.time()
                    })
    except asyncio.CancelledError:
        pass


def schedule_turn(room, room_id, turn_symbol, turn_secs=TURN_SECS):
    """Hủy timeout cũ, set deadline mới, tạo task mới"""
    if room[0].get("task") and not room[0]["task"].done():
        room[0]["task"].cancel()
    room[0]["turn"] = turn_symbol
    room[0]["turn_deadline"] = time.time() + turn_secs
    room[0]["turn_secs"] = turn_secs
    # Chỉ schedule timeout nếu match có bật thời gian (time_limit > 0)
    if room[0].get("time_limit", 0) > 0:
        room[0]["task"] = asyncio.create_task(
            start_timeout(room_id, turn_symbol, turn_secs)
        )
    else:
        room[0]["task"] = None
        room[0]["turn_deadline"] = None


async def handler(ws):
    room_id = None
    player = None

    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        data = json.loads(raw)

        if data.get("action") != "join":
            await send(ws, {"type": "error", "msg": "Yêu cầu không hợp lệ"})
            return

        room_id = clean(data.get("room"), 32)
        name = clean(data.get("name"), 20, "Người chơi")

        try:
            time_limit = max(0, int(data.get("time_limit", 0)))
        except Exception:
            time_limit = 0

        board_size = data.get("board_size", "20x20")
        if board_size not in ("15x15", "19x19", "20x20"):
            board_size = "20x20"

        rule = clean(data.get("rule"), 32, "Tiêu chuẩn")

        if not room_id:
            await send(ws, {"type": "error", "msg": "Thiếu mã phòng"})
            return

        player = {
            "ws": ws,
            "name": name,
            "symbol": None,
            "task": None
        }

        async with rooms_lock:
            room = rooms.setdefault(room_id, [])

            if len(room) >= 2:
                await send(ws, {"type": "error", "msg": "Phòng đã đầy"})
                return

            room.append(player)

            if len(room) == 1:
                player["board_size"] = board_size
                player["rule"] = rule
                player["time_limit"] = time_limit

                await send(ws, {
                    "type": "waiting",
                    "msg": "Đã vào phòng. Đang chờ đối thủ..."
                })

            else:
                host = room[0]
                final_board = host.get("board_size", board_size)
                final_rule = host.get("rule", rule)
                final_time = host.get("time_limit", time_limit)

                if not host.get("board_size"):
                    final_board = board_size
                if not host.get("rule"):
                    final_rule = rule

                room[0]["symbol"] = "X"
                room[1]["symbol"] = "O"
                room[0]["time_limit"] = final_time
                room[0]["board_size"] = final_board
                room[0]["rule"] = final_rule

                for i, p in enumerate(room):
                    opp = room[1 - i]
                    await send(p["ws"], {
                        "type": "start",
                        "symbol": p["symbol"],
                        "opponent_name": opp["name"],
                        "board_size": final_board,
                        "rule": final_rule,
                        "time_limit": final_time,
                        "turn_secs": TURN_SECS
                    })

                room[0]["turn"] = "X"
                room[0]["turn_deadline"] = None
                room[0]["task"] = None

                for p in room:
                    await send(p["ws"], {
                        "type": "turn_start",
                        "symbol": "X",
                        "turn_secs": TURN_SECS,
                        "deadline": None,
                        "server_ts": time.time()
                    })

        async for msg in ws:
            try:
                payload = json.loads(msg)
            except Exception:
                continue

            async with rooms_lock:
                room = rooms.get(room_id)
                if not room:
                    break

                if len(room) < 2:
                    t = payload.get("type")
                    if t in ("update_settings", "update_time_limit"):
                        p0 = room[0]
                        if "board_size" in payload:
                            bs = payload["board_size"]
                            if bs in ("15x15", "19x19", "20x20"):
                                p0["board_size"] = bs
                        if "rule" in payload:
                            p0["rule"] = clean(payload["rule"], 32, "Tiêu chuẩn")
                        if "time_limit" in payload:
                            try:
                                p0["time_limit"] = max(0, int(payload["time_limit"]))
                            except Exception:
                                pass
                    continue

                sender = next((p for p in room if p["ws"] is ws), None)
                if not sender:
                    break

                t = payload.get("type")
                others = [p for p in room if p["ws"] is not ws]

                if t == "move":
                    r = payload.get("r")
                    c = payload.get("c")

                    if not (isinstance(r, int) and isinstance(c, int) and 0 <= r < 20 and 0 <= c < 20):
                        continue

                    current_turn = room[0].get("turn")
                    if current_turn != sender["symbol"]:
                        continue

                    next_turn = "O" if sender["symbol"] == "X" else "X"

                    schedule_turn(room, room_id, next_turn, TURN_SECS)
                    deadline = room[0].get("turn_deadline")
                    server_ts = time.time()

                    for p in others:
                        await send(p["ws"], payload)

                    for p in room:
                        await send(p["ws"], {
                            "type": "turn_start",
                            "symbol": next_turn,
                            "turn_secs": TURN_SECS,
                            "deadline": deadline,
                            "server_ts": server_ts
                        })

                elif t == "rematch":
                    if room[0].get("task") and not room[0]["task"].done():
                        room[0]["task"].cancel()

                    for p in room:
                        p["symbol"] = "O" if p["symbol"] == "X" else "X"

                    room[0]["turn"] = "X"
                    room[0]["turn_deadline"] = None
                    room[0]["task"] = None

                    for p in others:
                        await send(p["ws"], payload)

                    for p in room:
                        await send(p["ws"], {
                            "type": "turn_start",
                            "symbol": "X",
                            "turn_secs": TURN_SECS,
                            "deadline": None,
                            "server_ts": time.time()
                        })

                elif t == "timeout":
                    if room[0].get("task") and not room[0]["task"].done():
                        room[0]["task"].cancel()
                    room[0]["turn"] = None
                    room[0]["turn_deadline"] = None
                    for p in room:
                        await send(p["ws"], {
                            "type": "timeout",
                            "loser": payload.get("loser"),
                            "server_ts": time.time()
                        })

                elif t == "update_settings":
                    if "board_size" in payload:
                        bs = payload["board_size"]
                        if bs in ("15x15", "19x19", "20x20"):
                            room[0]["board_size"] = bs
                    if "rule" in payload:
                        room[0]["rule"] = clean(payload["rule"], 32, "Tiêu chuẩn")
                    if "time_limit" in payload:
                        try:
                            room[0]["time_limit"] = max(0, int(payload["time_limit"]))
                        except Exception:
                            pass

                    for p in others:
                        await send(p["ws"], {
                            "type": "update_settings",
                            "board_size": room[0].get("board_size", "20x20"),
                            "rule": room[0].get("rule", "Tiêu chuẩn"),
                            "time_limit": room[0].get("time_limit", 0)
                        })

                elif t == "update_time_limit":
                    try:
                        new_limit = max(0, int(payload.get("time_limit", 0)))
                        room[0]["time_limit"] = new_limit
                    except Exception:
                        pass
                    for p in others:
                        await send(p["ws"], payload)

                else:
                    for p in others:
                        await send(p["ws"], payload)

    except Exception:
        pass
    finally:
        if room_id and player:
            await remove_player(room_id, ws)


async def main():
    port = int(os.environ.get("PORT", 3000))
    print(f"Caro Ultra Server đang chạy trên port {port} | TURN_SECS={TURN_SECS}")
    async with websockets.serve(
        handler,
        "0.0.0.0",
        port,
        ping_interval=20,
        ping_timeout=20
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
