import asyncio
import json
import os
import time
from contextlib import suppress

import websockets

rooms = {}
rooms_lock = asyncio.Lock()

TURN_SECS = 35
MAX_TIME_LIMIT_SECONDS = 7 * 24 * 60 * 60
VALID_BOARDS = {"15x15": 15, "20x20": 20}
MAX_MESSAGE_BYTES = 64 * 1024


def clean(text, max_len=24, default=""):
    if not isinstance(text, str):
        return default
    text = " ".join(text.strip().split())
    return text[:max_len] if text else default


def normalize_rule(rule):
    """Chuẩn hóa luật về mã trung lập — không phụ thuộc ngôn ngữ client."""
    r = str(rule or "").strip().lower()
    if r in ("block_both_ends", "block"):
        return "block_both_ends"
    if "block" in r or "chặn 2" in r or "chan 2" in r:
        return "block_both_ends"
    return "standard"


def board_dimension(board_size):
    return VALID_BOARDS.get(board_size, 20)


def valid_int(value):
    return isinstance(value, int) and not isinstance(value, bool)

def parse_time_limit(value, default=0):
    """Parse a client-supplied match limit without allowing huge integers to poison state."""
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(MAX_TIME_LIMIT_SECONDS, max(0, value))


def opponent(symbol):
    return "O" if symbol == "X" else "X"


def room_state(room):
    return room[0] if room else None


def current_match_times(state, now=None):
    """Return display-safe integer match clocks without mutating room state."""
    now = time.time() if now is None else now
    remaining = dict(state.get("match_remaining", {"X": 0.0, "O": 0.0}))
    turn = state.get("turn")
    deadline = state.get("turn_deadline")
    if turn in ("X", "O") and deadline and state.get("time_limit", 0) > 0:
        # The turn deadline may be shorter than the total-match remaining time.
        # Only the active side's clock is running.
        active_left = max(0.0, deadline - now)
        turn_started = state.get("turn_started_at")
        if turn_started is not None:
            spent = max(0.0, now - float(turn_started))
        else:
            turn_secs = state.get("turn_secs", TURN_SECS)
            spent = max(0.0, turn_secs - active_left)
        remaining[turn] = max(0.0, remaining.get(turn, 0.0) - spent)
    return {"X": max(0, int(remaining.get("X", 0.0))),
            "O": max(0, int(remaining.get("O", 0.0)))}


def consume_active_turn(state, now=None):
    """Commit elapsed time for the current turn into precise match clocks."""
    now = time.time() if now is None else now
    turn = state.get("turn")
    deadline = state.get("turn_deadline")
    if turn not in ("X", "O") or not deadline or state.get("time_limit", 0) <= 0:
        return
    turn_secs = float(state.get("turn_secs", TURN_SECS))
    turn_started = state.get("turn_started_at")
    if turn_started is not None:
        spent = min(turn_secs, max(0.0, now - float(turn_started)))
    else:
        active_left = max(0.0, deadline - now)
        spent = min(turn_secs, max(0.0, turn_secs - active_left))
    remaining = state.setdefault("match_remaining", {"X": 0.0, "O": 0.0})
    remaining[turn] = max(0.0, float(remaining.get(turn, 0.0)) - spent)


def cancel_turn_task(state):
    """Cancel the active turn watchdog, but never cancel the task calling us."""
    task = state.get("task")
    current = asyncio.current_task()
    if task and task is not current and not task.done():
        task.cancel()
    state["task"] = None


def check_win(board, r, c, piece, rule):
    """Mirror the client's get_winning_line() logic for server authority."""
    n = len(board)
    is_standard = normalize_rule(rule) == "standard"
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        cells = [(r, c)]
        blocked_pos = blocked_neg = False

        nr, nc = r + dr, c + dc
        while 0 <= nr < n and 0 <= nc < n:
            if board[nr][nc] == piece:
                cells.append((nr, nc))
                nr += dr
                nc += dc
            else:
                blocked_pos = board[nr][nc] != ""
                break
        else:
            blocked_pos = True

        nr, nc = r - dr, c - dc
        while 0 <= nr < n and 0 <= nc < n:
            if board[nr][nc] == piece:
                cells.insert(0, (nr, nc))
                nr -= dr
                nc -= dc
            else:
                blocked_neg = board[nr][nc] != ""
                break
        else:
            blocked_neg = True

        if len(cells) >= 5:
            if is_standard:
                return cells
            # Luật chặn 2 đầu: bị chặn cả hai đầu thì không thắng
            if blocked_pos and blocked_neg:
                continue
            return cells
    return []


def make_board(size):
    return [["" for _ in range(size)] for _ in range(size)]


async def safe_send(ws, data):
    try:
        await ws.send(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        return True
    except Exception:
        return False


async def send_many(items):
    """Network I/O happens outside rooms_lock and in parallel."""
    if not items:
        return
    await asyncio.gather(*(safe_send(ws, data) for ws, data in items), return_exceptions=True)


async def start_timeout(room_id, expected_turn, expected_deadline):
    """Server-authoritative timeout. Client timeout packets can never force a loss."""
    try:
        delay = max(0.0, expected_deadline - time.time())
        await asyncio.sleep(delay)
        outbound = []
        async with rooms_lock:
            room = rooms.get(room_id)
            if not room or len(room) < 2:
                return
            state = room_state(room)
            if (state.get("turn") != expected_turn or
                    state.get("turn_deadline") != expected_deadline or
                    state.get("game_over")):
                return

            now = time.time()
            consume_active_turn(state, now)
            state["turn"] = None
            state["turn_deadline"] = None
            state["turn_started_at"] = None
            cancel_turn_task(state)
            state["game_over"] = True
            state["winner"] = opponent(expected_turn)
            times = current_match_times(state, now)
            payload = {
                "type": "timeout",
                "loser": expected_turn,
                "times": times,
                "server_ts": now,
            }
            outbound = [(p["ws"], payload) for p in room]
        await send_many(outbound)
    except asyncio.CancelledError:
        pass


def schedule_turn_locked(room, room_id, turn_symbol, turn_secs=TURN_SECS):
    """Update turn state. Caller MUST hold rooms_lock."""
    state = room_state(room)
    now = time.time()
    old_turn = state.get("turn")
    if old_turn in ("X", "O"):
        consume_active_turn(state, now)
    cancel_turn_task(state)

    state["turn"] = turn_symbol
    state["turn_secs"] = float(turn_secs)
    state["turn_started_at"] = now

    if state.get("time_limit", 0) > 0:
        remaining = max(0.0, float(state.setdefault("match_remaining", {}).get(turn_symbol, 0.0)))
        if remaining <= 0:
            state["turn_deadline"] = now
        else:
            state["turn_deadline"] = now + min(float(turn_secs), remaining)
        deadline = state["turn_deadline"]
        state["task"] = asyncio.create_task(start_timeout(room_id, turn_symbol, deadline))
    else:
        state["turn_deadline"] = None
        state["task"] = None


def make_settings(state, player):
    own = player.get("symbol", "X")
    return {
        "board_size": state.get("board_size", "20x20"),
        "rule": normalize_rule(state.get("rule", "standard")),
        "time_limit": state.get("time_limit", 0),
        "auto_rotate": bool(state.get("auto_rotate", True)),
        "times": current_match_times(state),
        "symbol": own,
        "opponent_symbol": opponent(own),
    }


async def remove_player(room_id, ws):
    outbound = []
    task = None
    async with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            return
        player = next((p for p in room if p["ws"] is ws), None)
        if not player:
            return
        room.remove(player)
        if not room:
            rooms.pop(room_id, None)
            return
        state = room_state(room)
        # Force clear turn nếu chỉ còn 1 người
        if len(room) == 1:
            cancel_turn_task(state)
            state["turn"] = None
            state["turn_deadline"] = None
            state["turn_started_at"] = None
            state["game_over"] = True
        for p in room:
            outbound.append((p["ws"], {
                "type": "disconnect",
                "msg_key": "online_opp_left",
                "msg": "Đối thủ đã thoát.",
            }))
    if task:
        with suppress(asyncio.CancelledError):
            await asyncio.sleep(0)
    await send_many(outbound)


async def handler(ws):
    room_id = None
    player = None
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        data = json.loads(raw)

        if data.get("action") == "warmup":
            await safe_send(ws, {"type": "warmup_ok"})
            return
        if data.get("action") != "join":
            await safe_send(ws, {"type": "error", "msg_key": "online_invalid_request", "msg": "Yêu cầu không hợp lệ"})
            return

        room_id = clean(data.get("room"), 32)
        name = clean(data.get("name"), 20, "Người chơi")
        time_limit = parse_time_limit(data.get("time_limit", 0))
        board_size = data.get("board_size", "20x20")
        if board_size not in VALID_BOARDS:
            board_size = "20x20"
        rule = normalize_rule(data.get("rule"))
        req_symbol = data.get("symbol") if data.get("symbol") in ("X", "O") else "X"
        if not room_id:
            await safe_send(ws, {"type": "error", "msg_key": "online_need_room", "msg": "Thiếu mã phòng"})
            return

        player = {
            "ws": ws,
            "name": name,
            "symbol": req_symbol,
            "rematch_ready": False,
        }
        outbound = []
        close_old = None

        async with rooms_lock:
            room = rooms.setdefault(room_id, [])
            # Remove stale sockets without doing network I/O under the lock.
            room[:] = [p for p in room if not getattr(p["ws"], "closed", False)]

            if len(room) >= 2:
                duplicate = next((p for p in room if p["name"] == name), None)
                if duplicate:
                    close_old = duplicate["ws"]
                    room.remove(duplicate)
                    state = room_state(room) if room else None
                    if state:
                        cancel_turn_task(state)
                else:
                    outbound.append((ws, {"type": "error", "msg_key": "online_room_full", "msg": "Phòng đã đầy"}))

            if outbound:
                pass
            else:
                room.append(player)
                if len(room) == 1:
                    player.update({
                        "board_size": board_size,
                        "rule": rule,
                        "time_limit": time_limit,
                        "auto_rotate": True,
                    })
                    outbound.append((ws, {"type": "waiting", "msg_key": "online_waiting", "msg": "Đã vào phòng. Đang chờ đối thủ..."}))
                else:
                    host = room[0]
                    final_board = host.get("board_size") or board_size
                    final_rule = normalize_rule(host.get("rule") or rule)
                    final_time = parse_time_limit(host.get("time_limit", time_limit), time_limit)
                    host_sym = host.get("symbol", "X")
                    player["symbol"] = req_symbol if req_symbol != host_sym else opponent(host_sym)
                    state = host
                    state.update({
                        "time_limit": final_time,
                        "board_size": final_board if final_board in VALID_BOARDS else "20x20",
                        "rule": final_rule,
                        "match_remaining": {"X": float(final_time), "O": float(final_time)},
                        "turn": None,
                        "turn_deadline": None,
                        "turn_secs": TURN_SECS,
                        "task": None,
                        "auto_rotate": bool(state.get("auto_rotate", True)),
                        "board": make_board(board_dimension(final_board)),
                        "game_over": False,
                        "winner": None,
                    })
                    for p in room:
                        p["rematch_ready"] = False

                    for p in room:
                        opp = room[1] if p is room[0] else room[0]
                        outbound.append((p["ws"], {
                            "type": "start",
                            "symbol": p["symbol"],
                            "opponent_name": opp["name"],
                            "board_size": state["board_size"],
                            "rule": state["rule"],
                            "time_limit": final_time,
                            "auto_rotate": state["auto_rotate"],
                            "turn_secs": TURN_SECS,
                            "times": {"X": final_time, "O": final_time},
                        }))

                    # Lượt đầu: X đi trước nhưng CHƯA bật đồng hồ — chỉ đếm sau nước đi đầu.
                    cancel_turn_task(state)
                    state["turn"] = "X"
                    state["turn_secs"] = float(TURN_SECS)
                    state["turn_deadline"] = None
                    state["turn_started_at"] = None
                    state["task"] = None
                    now = time.time()
                    times = current_match_times(state, now)
                    for p in room:
                        outbound.append((p["ws"], {
                            "type": "turn_start",
                            "symbol": "X",
                            "turn_secs": TURN_SECS,
                            "deadline": None,
                            "times": times,
                            "server_ts": now,
                        }))

        if close_old:
            with suppress(Exception):
                await close_old.close()
        await send_many(outbound)
        if outbound and any(item[1].get("msg_key") == "online_room_full" for item in outbound):
            return

        async for msg in ws:
            if isinstance(msg, bytes):
                if len(msg) > MAX_MESSAGE_BYTES:
                    continue
                msg = msg.decode("utf-8", "replace")
            elif len(msg.encode("utf-8", "ignore")) > MAX_MESSAGE_BYTES:
                continue
            try:
                payload = json.loads(msg)
            except (TypeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue

            outbound = []
            close_sender = False
            do_leave = False
            async with rooms_lock:
                room = rooms.get(room_id)
                if not room:
                    break
                sender = next((p for p in room if p["ws"] is ws), None)
                if not sender:
                    break
                state = room_state(room)
                t = payload.get("type")

                if t == "leave":
                    # Client chủ động báo thoát → xử lý ngay, không chờ TCP/ping timeout
                    do_leave = True
                elif len(room) < 2:
                    if t == "symbol_update":
                        # Trước khi trận bắt đầu, người chơi vẫn được đổi X/O/Tự động.
                        # Phòng chờ chưa có bàn cờ nên chưa có nước đi để khóa lựa chọn.
                        new_sym = payload.get("symbol")
                        if new_sym in ("X", "O"):
                            sender["symbol"] = new_sym
                        if "auto_rotate" in payload:
                            sender["auto_rotate"] = bool(payload["auto_rotate"])
                        own = sender.get("symbol", "X")
                        outbound.append((ws, {
                            "type": "symbol_update",
                            "symbol": own,
                            "opponent_symbol": opponent(own),
                            "auto_rotate": bool(sender.get("auto_rotate", True)),
                        }))
                    elif t in ("update_settings", "update_time_limit"):
                        if "board_size" in payload and payload["board_size"] in VALID_BOARDS:
                            sender["board_size"] = payload["board_size"]
                        if "rule" in payload:
                            sender["rule"] = normalize_rule(payload["rule"])
                        if "time_limit" in payload:
                            try:
                                sender["time_limit"] = max(0, int(payload["time_limit"]))
                            except (TypeError, ValueError):
                                pass
                        if "auto_rotate" in payload:
                            sender["auto_rotate"] = bool(payload["auto_rotate"])
                        if payload.get("symbol") in ("X", "O"):
                            sender["symbol"] = payload["symbol"]
                        own = sender.get("symbol", "X")
                        outbound.extend([
                            (ws, {"type": "symbol_update", "symbol": own,
                                  "opponent_symbol": opponent(own),
                                  "auto_rotate": bool(sender.get("auto_rotate", True))}),
                            (ws, {"type": "update_settings", **make_settings(sender, sender)}),
                        ])
                    elif t == "chat":
                        text = clean(payload.get("text"), 500)
                        if text:
                            outbound.append((ws, {"type": "chat", "name": sender["name"], "text": text}))
                    # Other game messages are ignored while waiting.
                else:
                    others = [p for p in room if p["ws"] is not ws]

                    if t == "move":
                        r, c = payload.get("r"), payload.get("c")
                        n = board_dimension(state.get("board_size", "20x20"))
                        reason = None
                        if state.get("game_over"):
                            reason = "game_over"
                        elif state.get("turn") != sender.get("symbol"):
                            reason = "not_your_turn"
                        elif not (valid_int(r) and valid_int(c) and 0 <= r < n and 0 <= c < n):
                            reason = "invalid_cell"
                        elif state["board"][r][c] != "":
                            reason = "occupied"

                        if reason:
                            outbound.append((ws, {"type": "move_rejected", "reason": reason}))
                        else:
                            now = time.time()
                            # A move arriving after the server deadline is a timeout, not a valid move.
                            deadline = state.get("turn_deadline")
                            if deadline and now >= deadline:
                                consume_active_turn(state, now)
                                cancel_turn_task(state)
                                loser = state["turn"]
                                state["turn"] = None
                                state["turn_deadline"] = None
                                state["turn_started_at"] = None
                                state["game_over"] = True
                                state["winner"] = opponent(loser)
                                times = current_match_times(state, now)
                                timeout_payload = {"type": "timeout", "loser": loser, "times": times, "server_ts": now}
                                outbound.extend((p["ws"], timeout_payload) for p in room)
                            else:
                                state["board"][r][c] = sender["symbol"]
                                state["last_move"] = (r, c)
                                consume_active_turn(state, now)
                                cancel_turn_task(state)
                                move_payload = {"type": "move", "r": r, "c": c}
                                for p in others:
                                    outbound.append((p["ws"], move_payload))

                                win_line = check_win(state["board"], r, c, sender["symbol"], state.get("rule"))
                                if win_line:
                                    state["game_over"] = True
                                    state["winner"] = sender["symbol"]
                                    state["turn"] = None
                                    state["turn_deadline"] = None
                                    state["turn_started_at"] = None
                                    result = {
                                        "type": "game_result",
                                        "result": "win",
                                        "winner": sender["symbol"],
                                        "line": win_line,
                                    }
                                    outbound.extend((p["ws"], result) for p in room)
                                elif all(cell != "" for row in state["board"] for cell in row):
                                    state["game_over"] = True
                                    state["winner"] = None
                                    state["turn"] = None
                                    state["turn_deadline"] = None
                                    state["turn_started_at"] = None
                                    result = {"type": "game_result", "result": "draw", "winner": None, "line": []}
                                    outbound.extend((p["ws"], result) for p in room)
                                else:
                                    next_turn = opponent(sender["symbol"])
                                    schedule_turn_locked(room, room_id, next_turn, TURN_SECS)
                                    times = current_match_times(state, now)
                                    turn_payload = {
                                        "type": "turn_start",
                                        "symbol": next_turn,
                                        "turn_secs": TURN_SECS,
                                        "deadline": state.get("turn_deadline"),
                                        "times": times,
                                        "server_ts": now,
                                    }
                                    outbound.extend((p["ws"], turn_payload) for p in room)

                    elif t == "timeout":
                        # Never trust the client's loser value or local clock.
                        now = time.time()
                        if state.get("game_over") or state.get("turn") != sender.get("symbol"):
                            continue
                        deadline = state.get("turn_deadline")
                        if not deadline or now < deadline:
                            continue
                        consume_active_turn(state, now)
                        cancel_turn_task(state)
                        loser = state["turn"]
                        state["turn"] = None
                        state["turn_deadline"] = None
                        state["game_over"] = True
                        state["winner"] = opponent(loser)
                        times = current_match_times(state, now)
                        outbound.extend((p["ws"], {
                            "type": "timeout", "loser": loser, "times": times, "server_ts": now
                        }) for p in room)

                    elif t == "resign":
                        # Đầu hàng giữa ván — chỉ hợp lệ khi chưa game_over và đã có nước
                        has_moves = bool(state.get("board")) and any(
                            any(cell != "" for cell in row) for row in state["board"]
                        )
                        if state.get("game_over") or not has_moves:
                            continue
                        if sender.get("rematch_ready"):
                            continue
                        now = time.time()
                        consume_active_turn(state, now)
                        cancel_turn_task(state)
                        loser = sender.get("symbol")
                        winner = opponent(loser) if loser in ("X", "O") else None
                        state["game_over"] = True
                        state["winner"] = winner
                        state["turn"] = None
                        state["turn_deadline"] = None
                        state["turn_started_at"] = None
                        sender["rematch_ready"] = True
                        times = current_match_times(state, now)
                        resign_payload = {
                            "type": "game_result",
                            "result": "resign",
                            "winner": winner,
                            "resigned_by": sender.get("name", ""),
                            "resigned_symbol": loser,
                            "line": [],
                            "times": times,
                            "server_ts": now,
                        }
                        outbound.extend((p["ws"], resign_payload) for p in room)
                        outbound.extend((p["ws"], {
                            "type": "rematch_waiting",
                            "ready_symbol": sender.get("symbol"),
                            "resigned_by": sender.get("name", ""),
                            "resigned_symbol": loser,
                        }) for p in room)

                    elif t == "rematch":
                        sender["rematch_ready"] = True
                        # Báo ngay cho cả phòng biết một người đã READY.
                        outbound.extend((p["ws"], {
                            "type": "rematch_waiting",
                            "ready_symbol": sender.get("symbol")
                        }) for p in room)
                        if all(p.get("rematch_ready", False) for p in room):
                            if state.get("auto_rotate", True):
                                for p in room:
                                    p["symbol"] = opponent(p["symbol"])
                            cancel_turn_task(state)
                            limit = int(state.get("time_limit", 0))
                            state["match_remaining"] = {"X": float(limit), "O": float(limit)}
                            state["board"] = make_board(board_dimension(state.get("board_size", "20x20")))
                            state["game_over"] = False
                            state["winner"] = None
                            state["last_move"] = None
                            state["turn"] = None
                            state["turn_deadline"] = None
                            state["turn_started_at"] = None
                            for p in room:
                                p["rematch_ready"] = False
                                outbound.append((p["ws"], {
                                    "type": "rematch",
                                    "symbol": p["symbol"],
                                    "auto_rotate": bool(state.get("auto_rotate", True)),
                                }))
                            # Ván mới: X đi trước nhưng chưa bật đồng hồ
                            state["turn"] = "X"
                            state["turn_secs"] = float(TURN_SECS)
                            state["turn_deadline"] = None
                            state["turn_started_at"] = None
                            state["task"] = None
                            now = time.time()
                            times = current_match_times(state, now)
                            outbound.extend((p["ws"], {
                                "type": "turn_start", "symbol": "X", "turn_secs": TURN_SECS,
                                "deadline": None, "times": times, "server_ts": now
                            }) for p in room)

                    elif t == "symbol_update":
                        # Sau nước đầu tiên, server khóa X/O/Tự động để client
                        # không thể bypass trạng thái disabled bằng packet thủ công.
                        has_moves = bool(state.get("board")) and any(
                            any(cell != "" for cell in row) for row in state["board"]
                        )
                        applied = False
                        if not has_moves:
                            new_sym = payload.get("symbol")
                            if new_sym not in ("X", "O"):
                                continue
                            if sender.get("symbol") != new_sym:
                                applied = True
                            sender["symbol"] = new_sym
                            for p in others:
                                p["symbol"] = opponent(new_sym)
                            if "auto_rotate" in payload:
                                new_auto = bool(payload["auto_rotate"])
                                if bool(state.get("auto_rotate", True)) != new_auto:
                                    applied = True
                                state["auto_rotate"] = new_auto
                        if applied or not has_moves:
                            changer = sender.get("name", "")
                            for p in room:
                                outbound.append((p["ws"], {
                                    "type": "symbol_update",
                                    "symbol": p["symbol"],
                                    "opponent_symbol": opponent(p["symbol"]),
                                    "auto_rotate": bool(state.get("auto_rotate", False)),
                                    "changed_by": changer,
                                    "notify": p["ws"] is not ws,
                                }))

                    elif t in ("update_settings", "update_time_limit"):
                        # Settings are only applied safely before the first move.
                        has_moves = bool(state.get("board")) and any(
                            any(cell != "" for cell in row) for row in state["board"]
                        )
                        changed_fields = []
                        if state.get("game_over") or not has_moves:
                            if payload.get("board_size") in VALID_BOARDS:
                                if state.get("board_size") != payload["board_size"]:
                                    changed_fields.append("board_size")
                                state["board_size"] = payload["board_size"]
                                state["board"] = make_board(board_dimension(state["board_size"]))
                            if "rule" in payload:
                                new_rule = normalize_rule(payload["rule"])
                                if normalize_rule(state.get("rule")) != new_rule:
                                    changed_fields.append("rule")
                                state["rule"] = new_rule
                            if "time_limit" in payload:
                                new_limit = parse_time_limit(payload["time_limit"], state.get("time_limit", 0))
                                if int(state.get("time_limit", 0)) != int(new_limit):
                                    changed_fields.append("time_limit")
                                state["time_limit"] = new_limit
                                if not has_moves:
                                    # Chưa có nước → chỉ reset số phút, không bật đếm
                                    state["match_remaining"] = {
                                        "X": float(new_limit), "O": float(new_limit)
                                    }
                                    cancel_turn_task(state)
                                    state["turn_deadline"] = None
                                    state["turn_started_at"] = None
                                    state["task"] = None
                        if "auto_rotate" in payload:
                            new_auto = bool(payload["auto_rotate"])
                            if bool(state.get("auto_rotate", True)) != new_auto:
                                changed_fields.append("auto_rotate")
                            state["auto_rotate"] = new_auto
                        if not has_moves and payload.get("symbol") in ("X", "O"):
                            if sender.get("symbol") != payload["symbol"]:
                                changed_fields.append("symbol")
                            sender["symbol"] = payload["symbol"]
                            for p in others:
                                p["symbol"] = opponent(sender["symbol"])
                        changer = sender.get("name", "")
                        for p in room:
                            outbound.append((p["ws"], {
                                "type": "update_settings",
                                **make_settings(state, p),
                                "changed_by": changer,
                                "changed_fields": changed_fields,
                                "notify": p["ws"] is not ws,
                            }))

                    elif t == "chat":
                        text = clean(payload.get("text"), 500)
                        if text:
                            outbound.extend((p["ws"], {"type": "chat", "name": sender["name"], "text": text}) for p in room)

                    else:
                        # Keep compatibility for harmless future/non-game messages.
                        for p in others:
                            outbound.append((p["ws"], payload))

            await send_many(outbound)
            if do_leave:
                player["_left"] = True
                await remove_player(room_id, ws)
                break

    except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
        pass
    except Exception:
        # A single malformed client must never bring down the server.
        pass
    finally:
        if room_id and player and not player.get("_left"):
            await remove_player(room_id, ws)


async def main():
    port = int(os.environ.get("PORT", 3000))
    print(f"XOUltra-AI Server port {port} | TURN_SECS={TURN_SECS}")
    async with websockets.serve(
        handler,
        "0.0.0.0",
        port,
        ping_interval=15,
        ping_timeout=8,
        max_size=MAX_MESSAGE_BYTES,
        max_queue=32,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
