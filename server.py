import asyncio
import json
import os
import websockets

rooms = {}
rooms_lock = asyncio.Lock()

def clean(text, max_len=24, default=""):
    if not isinstance(text, str):
        return default
    text = " ".join(text.strip().split())
    return text[:max_len] if text else default

async def send(ws, data):
    try:
        await ws.send(json.dumps(data, ensure_ascii=False))
    except:
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
        if player.get("task") and not player["task"].done():
            player["task"].cancel()
        remaining = list(room)
        if not remaining:
            del rooms[room_id]
    for p in remaining:
        await send(p["ws"], {"type": "disconnect", "msg": "Đối thủ đã thoát."})

async def handler(ws):
    room_id = None
    player = None
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=12)
        data = json.loads(raw)

        if data.get("action") != "join":
            await send(ws, {"type": "error", "msg": "Yêu cầu không hợp lệ"})
            return

        room_id = clean(data.get("room"), 32)
        name = clean(data.get("name"), 20, "Người chơi")
        try:
            time_limit = max(0, int(data.get("time_limit", 0)))
        except:
            time_limit = 0

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
                await send(ws, {
                    "type": "waiting",
                    "msg": "Đã vào phòng. Đang chờ đối thủ..."
                })
                return

            # 2 người → bắt đầu
            room[0]["symbol"] = "X"
            room[1]["symbol"] = "O"
            room[0]["turn"] = "X"
            room[0]["time_limit"] = time_limit

            for i, p in enumerate(room):
                opp = room[1 - i]
                await send(p["ws"], {
                    "type": "start",
                    "symbol": p["symbol"],
                    "opponent_name": opp["name"]
                })
                await send(p["ws"], {
                    "type": "turn_start",
                    "symbol": "X"
                })

        # Relay
        async for msg in ws:
            try:
                payload = json.loads(msg)
            except:
                continue

            async with rooms_lock:
                room = rooms.get(room_id)
                if not room or len(room) < 2:
                    break

                sender = next((p for p in room if p["ws"] is ws), None)
                if not sender:
                    break

                t = payload.get("type")
                other = [p for p in room if p["ws"] is not ws]

                if t == "move":
                    r, c = payload.get("r"), payload.get("c")
                    if not (isinstance(r, int) and isinstance(c, int) and 0 <= r < 20 and 0 <= c < 20):
                        continue
                    if room[0].get("turn") != sender["symbol"]:
                        continue

                    # đổi lượt
                    room[0]["turn"] = "O" if sender["symbol"] == "X" else "X"
                    next_turn = room[0]["turn"]

                    # hủy timeout cũ
                    if room[0].get("task") and not room[0]["task"].done():
                        room[0]["task"].cancel()

                    # gửi move + turn_start
                    for p in other:
                        await send(p["ws"], payload)
                    for p in room:
                        await send(p["ws"], {"type": "turn_start", "symbol": next_turn})

                    # tạo timeout mới
                    limit = room[0].get("time_limit", 0)
                    if limit > 0:
                        async def timeout(expected):
                            try:
                                await asyncio.sleep(limit)
                                async with rooms_lock:
                                    r = rooms.get(room_id)
                                    if r and r[0].get("turn") == expected:
                                        r[0]["turn"] = None
                                        for p in r:
                                            await send(p["ws"], {"type": "timeout", "loser": expected})
                            except asyncio.CancelledError:
                                pass
                        room[0]["task"] = asyncio.create_task(timeout(next_turn))

                elif t == "rematch":
                    if room[0].get("task") and not room[0]["task"].done():
                        room[0]["task"].cancel()
                    # flip
                    for p in room:
                        p["symbol"] = "O" if p["symbol"] == "X" else "X"
                    room[0]["turn"] = "X"
                    for p in other:
                        await send(p["ws"], payload)
                    for p in room:
                        await send(p["ws"], {"type": "turn_start", "symbol": "X"})

                elif t == "timeout":
                    if room[0].get("task") and not room[0]["task"].done():
                        room[0]["task"].cancel()
                    room[0]["turn"] = None
                    for p in room:
                        await send(p["ws"], {"type": "timeout", "loser": payload.get("loser")})

                elif t == "update_time_limit":
                    try:
                        room[0]["time_limit"] = max(0, int(payload.get("time_limit", 0)))
                    except:
                        pass
                    for p in other:
                        await send(p["ws"], payload)

                else:
                    for p in other:
                        await send(p["ws"], payload)

    except:
        pass
    finally:
        if room_id and player:
            await remove_player(room_id, ws)

async def main():
    port = int(os.environ.get("PORT", 3000))
    print(f"Caro Server chạy port {port}")
    async with websockets.serve(handler, "0.0.0.0", port, ping_interval=20, ping_timeout=20):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())