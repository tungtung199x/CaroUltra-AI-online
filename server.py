import asyncio
import json
import os
import time
import websockets

rooms = {}
rooms_lock = asyncio.Lock()

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
        if remaining[0].get("task") and not remaining[0]["task"].done():
            try:
                remaining[0]["task"].cancel()
            except Exception:
                pass
    for p in remaining:
        await send(p["ws"], {"type": "disconnect", "msg": "Đối thủ đã thoát."})


def get_match_times(room0):
    """Trả về times đã trừ thời gian đã trôi của lượt hiện tại (nếu đang đếm)."""
    times = dict(room0.get("match_times", {"X": 0, "O": 0}))
    turn = room0.get("turn")
    deadline = room0.get("turn_deadline")
    turn_secs = room0.get("turn_secs", TURN_SECS)
    if turn and deadline and room0.get("time_limit", 0) > 0:
        elapsed = max(0.0, turn_secs - max(0.0, deadline - time.time()))
        # trừ vào người đang đi
        times[turn] = max(0, int(round(times.get(turn, 0) - elapsed)))
    return times


async def start_timeout(room_id, expected_turn, turn_secs):
    try:
        await asyncio.sleep(turn_secs)
        async with rooms_lock:
            room = rooms.get(room_id)
            if not room or len(room) < 2:
                return
            if room[0].get("turn") != expected_turn:
                return
            # Trừ hết turn vào match time
            mt = room[0].setdefault("match_times", {"X": 0, "O": 0})
            mt[expected_turn] = max(0, int(mt.get(expected_turn, 0) - turn_secs))
            room[0]["turn"] = None
            room[0]["turn_deadline"] = None
            times = dict(mt)
            for p in room:
                await send(p["ws"], {
                    "type": "timeout",
                    "loser": expected_turn,
                    "times": times,
                    "server_ts": time.time()
                })
    except asyncio.CancelledError:
        pass


def schedule_turn(room, room_id, turn_symbol, turn_secs=TURN_SECS):
    """Kết thúc lượt cũ (trừ thời gian đã dùng) rồi bắt đầu lượt mới."""
    r0 = room[0]
    old_turn = r0.get("turn")
    old_deadline = r0.get("turn_deadline")
    old_secs = r0.get("turn_secs", TURN_SECS)

    # Hủy task cũ
    if r0.get("task") and not r0["task"].done():
        r0["task"].cancel()

    # Trừ thời gian đã dùng của lượt cũ vào match_times
    if old_turn and old_deadline and r0.get("time_limit", 0) > 0:
        elapsed = max(0.0, old_secs - max(0.0, old_deadline - time.time()))
        mt = r0.setdefault("match_times", {"X": 0, "O": 0})
        mt[old_turn] = max(0, int(round(mt.get(old_turn, 0) - elapsed)))

    r0["turn"] = turn_symbol
    r0["turn_secs"] = turn_secs

    if r0.get("time_limit", 0) > 0:
        r0["turn_deadline"] = time.time() + turn_secs
        r0["task"] = asyncio.create_task(
            start_timeout(room_id, turn_symbol, turn_secs)
        )
    else:
        r0["turn_deadline"] = None
        r0["task"] = None


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

        player = {"ws": ws, "name": name, "symbol": None, "task": None}

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
                await send(ws, {"type": "waiting", "msg": "Đã vào phòng. Đang chờ đối thủ..."})
            else:
                host = room[0]
                final_board = host.get("board_size") or board_size
                final_rule = host.get("rule") or rule
                final_time = host.get("time_limit", time_limit)
                if final_board not in ("15x15", "19x19", "20x20"):
                    final_board = "20x20"

                room[0]["symbol"] = "X"
                room[1]["symbol"] = "O"
                room[0]["time_limit"] = final_time
                room[0]["board_size"] = final_board
                room[0]["rule"] = final_rule
                room[0]["match_times"] = {"X": final_time, "O": final_time}
                room[0]["turn"] = "X"
                room[0]["turn_deadline"] = None
                room[0]["task"] = None

                for i, p in enumerate(room):
                    opp = room[1 - i]
                    await send(p["ws"], {
                        "type": "start",
                        "symbol": p["symbol"],
                        "opponent_name": opp["name"],
                        "board_size": final_board,
                        "rule": final_rule,
                        "time_limit": final_time,
                        "turn_secs": TURN_SECS,
                        "times": {"X": final_time, "O": final_time}
                    })
                    await send(p["ws"], {
                        "type": "turn_start",
                        "symbol": "X",
                        "turn_secs": TURN_SECS,
                        "deadline": None,
                        "times": {"X": final_time, "O": final_time},
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
                    r, c = payload.get("r"), payload.get("c")
                    if not (isinstance(r, int) and isinstance(c, int) and 0 <= r < 20 and 0 <= c < 20):
                        continue
                    if room[0].get("turn") != sender["symbol"]:
                        continue

                    next_turn = "O" if sender["symbol"] == "X" else "X"
                    schedule_turn(room, room_id, next_turn, TURN_SECS)

                    deadline = room[0].get("turn_deadline")
                    times = get_match_times(room[0])
                    # get_match_times đã trừ elapsed của lượt MỚI — cần times SAU khi trừ lượt cũ
                    # schedule_turn đã trừ lượt cũ vào match_times; get_match_times sẽ trừ thêm elapsed lượt mới (~0)
                    times = dict(room[0].get("match_times", {"X": 0, "O": 0}))
                    server_ts = time.time()

                    for p in others:
                        await send(p["ws"], payload)

                    for p in room:
                        await send(p["ws"], {
                            "type": "turn_start",
                            "symbol": next_turn,
                            "turn_secs": TURN_SECS,
                            "deadline": deadline,
                            "times": times,
                            "server_ts": server_ts
                        })

                elif t == "rematch":
                    if room[0].get("task") and not room[0]["task"].done():
                        room[0]["task"].cancel()
                    for p in room:
                        p["symbol"] = "O" if p["symbol"] == "X" else "X"
                    limit = room[0].get("time_limit", 0)
                    room[0]["match_times"] = {"X": limit, "O": limit}
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
                            "times": {"X": limit, "O": limit},
                            "server_ts": time.time()
                        })

                elif t == "timeout":
                    if room[0].get("task") and not room[0]["task"].done():
                        room[0]["task"].cancel()
                    loser = payload.get("loser")
                    # Trừ nốt turn vào match time
                    if loser and room[0].get("turn_deadline"):
                        elapsed = max(0.0, room[0].get("turn_secs", TURN_SECS) - max(0.0, room[0]["turn_deadline"] - time.time()))
                        mt = room[0].setdefault("match_times", {"X": 0, "O": 0})
                        mt[loser] = max(0, int(round(mt.get(loser, 0) - elapsed)))
                    room[0]["turn"] = None
                    room[0]["turn_deadline"] = None
                    times = dict(room[0].get("match_times", {"X": 0, "O": 0}))
                    for p in room:
                        await send(p["ws"], {
                            "type": "timeout",
                            "loser": loser,
                            "times": times,
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
                            new_limit = max(0, int(payload["time_limit"]))
                            room[0]["time_limit"] = new_limit
                            # Reset match times nếu chưa có nước
                            if room[0].get("turn_deadline") is None:
                                room[0]["match_times"] = {"X": new_limit, "O": new_limit}
                        except Exception:
                            pass
                    for p in others:
                        await send(p["ws"], {
                            "type": "update_settings",
                            "board_size": room[0].get("board_size", "20x20"),
                            "rule": room[0].get("rule", "Tiêu chuẩn"),
                            "time_limit": room[0].get("time_limit", 0),
                            "times": dict(room[0].get("match_times", {"X": 0, "O": 0}))
                        })

                elif t == "update_time_limit":
                    try:
                        new_limit = max(0, int(payload.get("time_limit", 0)))
                        room[0]["time_limit"] = new_limit
                        if room[0].get("turn_deadline") is None:
                            room[0]["match_times"] = {"X": new_limit, "O": new_limit}
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
    print(f"Caro Ultra Server port {port} | TURN_SECS={TURN_SECS}")
    async with websockets.serve(handler, "0.0.0.0", port, ping_interval=20, ping_timeout=20):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
