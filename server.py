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
            await send(ws, {"type": "error", "msg": "Yêu cầu không hợp lệ