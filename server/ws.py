"""WebSocket endpoints: one per player, plus spectators."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.matches import MATCHES, PROTOCOL, TOKENS

router = APIRouter()


@router.websocket("/ws/play")
async def play(ws: WebSocket, token: str = "") -> None:
    if token not in TOKENS:
        await ws.close(code=4401)
        return
    match_id, pid = TOKENS[token]
    match = MATCHES[match_id]
    await ws.accept()
    match.conns[pid] = ws  # reconnect just replaces the socket
    await ws.send_json(
        {
            "v": PROTOCOL,
            "type": "welcome",
            "match_id": match_id,
            "you": pid,
            "status": match.status,
            "players": match.player_ids,
            "budget_left": match.budget_left(pid),
            "deadline_ms": match.deadline_ms,
        }
    )
    if match.status == "running":
        await ws.send_json(match.state_msg(pid))
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "move":
                match.submit(pid, msg.get("tick", -1), msg.get("move", ""))
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        if match.conns.get(pid) is ws:
            match.conns.pop(pid, None)
            match._check_all_in()  # don't make the tick loop wait for a ghost


@router.websocket("/ws/spectate")
async def spectate(ws: WebSocket, match_id: str = "") -> None:
    match = MATCHES.get(match_id) or (list(MATCHES.values())[-1] if MATCHES else None)
    await ws.accept()
    if match is None:
        await ws.send_json({"v": PROTOCOL, "type": "error", "error": "no matches yet"})
        await ws.close()
        return
    match.spectators.add(ws)
    await match.broadcast()
    try:
        while True:
            await ws.receive_text()  # spectators talk only by hanging up
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        match.spectators.discard(ws)
