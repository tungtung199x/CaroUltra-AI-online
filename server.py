import asyncio
import websockets
import json
import os

rooms = {}

async def handler(websocket):
    room_id = None
    try:
        message = await websocket.recv()
        data = json.loads(message)
        
        if data.get("action") == "join":
            room_id = data.get("room")
            if room_id not in rooms:
                rooms[room_id] = []
            
            if len(rooms[room_id]) >= 2:
                await websocket.send(json.dumps({"type": "error", "msg": "Phòng đã đầy! Vui lòng chọn mã khác."}))
                return

            rooms[room_id].append(websocket)
            
            # Đủ 2 người thì phát tín hiệu bắt đầu
            if len(rooms[room_id]) == 2:
                await rooms[room_id][0].send(json.dumps({"type": "start", "symbol": "X"}))
                await rooms[room_id][1].send(json.dumps({"type": "start", "symbol": "O"}))
            
            # Vòng lặp nhận và truyền tọa độ
            async for msg in websocket:
                for client in rooms[room_id]:
                    if client != websocket:
                        await client.send(msg)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if room_id and room_id in rooms and websocket in rooms[room_id]:
            rooms[room_id].remove(websocket)
            for client in rooms[room_id]:
                try:
                    await client.send(json.dumps({"type": "disconnect", "msg": "Đối thủ đã thoát hoặc mất mạng."}))
                except: pass
            if not rooms[room_id]:
                del rooms[room_id]

async def main():
    port = int(os.environ.get("PORT", 3000))
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())