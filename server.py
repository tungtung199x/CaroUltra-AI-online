import asyncio
import json
import os
import websockets

# ============================================================
# CARO ONLINE WEBSOCKET SERVER
# ============================================================
# Client gửi:
#   {"action": "join", "room": "1234", "name": "Tùng"}
#
# Khi đủ 2 người, server gửi cho mỗi client:
#   {
#       "type": "start",
#       "symbol": "X/O",
#       "player_name": "Tên của mình",
#       "opponent_name": "Tên đối thủ",
#       "room": "1234"
#   }
# ============================================================

rooms = {}
rooms_lock = asyncio.Lock()

MAX_NAME_LENGTH = 24
MAX_ROOM_LENGTH = 32


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
        remaining_players = list(room)

        if not remaining_players:
            del rooms[room_id]

    # Network I/O nằm ngoài lock để không khóa toàn bộ server.
    for opponent in remaining_players:
        await send_json(opponent["ws"], {
            "type": "disconnect",
            "msg": "Đối thủ đã thoát hoặc mất mạng.",
        })


async def handler(websocket):
    room_id = None
    player = None

    try:
        # --------------------------------------------------------
        # 1. Nhận yêu cầu JOIN đầu tiên
        # --------------------------------------------------------
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
        }

        start_messages = []
        opponent_joined_messages = []
        waiting_message = None

        # --------------------------------------------------------
        # 2. Thêm người chơi vào phòng
        # --------------------------------------------------------
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

                # Thông báo tên đối thủ.
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

                # Gửi start kèm tên của cả hai.
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

        # --------------------------------------------------------
        # 3. Gửi thông báo sau khi cập nhật room
        # --------------------------------------------------------
        if waiting_message:
            await send_json(websocket, waiting_message)

        for ws, message in opponent_joined_messages:
            await send_json(ws, message)

        for ws, message in start_messages:
            await send_json(ws, message)

        # --------------------------------------------------------
        # 4. Relay dữ liệu Caro
        # --------------------------------------------------------
        async for message in websocket:
            async with rooms_lock:
                room = rooms.get(room_id)

                if not room:
                    break

                clients = [
                    p["ws"]
                    for p in room
                    if p["ws"] is not websocket
                ]

            for client in clients:
                await relay_message(client, message)

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
    # Render/Railway/hosting thường cấp PORT qua biến môi trường.
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
