"""End-to-end: real uvicorn, real websockets, real SDK. Jev is in mock mode."""

import json
import threading
import time

import httpx
from websockets.sync.client import connect

from jevtron_sdk import Arena, Move, jev


def new_match(gm, players, **cfg):
    cfg.setdefault("deadline_ms", 300)
    cfg.setdefault("max_ticks", 30)
    cfg.setdefault("w", 20)
    cfg.setdefault("h", 20)
    r = gm.post("/matches", json={"players": players, **cfg})
    r.raise_for_status()
    return r.json()


def play(server, token, decide, results=None):
    arena = Arena(server, token, verbose=False)
    arena.on_tick(decide)
    out = arena.run()
    if results is not None:
        results.append(out)
    return out


def wait_connected(gm, match_id, n):
    for _ in range(200):
        meters = gm.get(f"/matches/{match_id}").json()["meters"]
        if sum(x["connected"] for x in meters) >= n:
            return
        time.sleep(0.05)
    raise AssertionError("bots never connected")


def run_bots(server, tokens, decide_by_player):
    results: list = []
    threads = [
        threading.Thread(target=play, args=(server, tok, decide_by_player[pid], results))
        for pid, tok in tokens.items()
    ]
    for t in threads:
        t.start()
    return threads, results


def test_four_clients_finish_a_match(server, gm):
    m = new_match(gm, ["a", "b", "c", "d"])
    decide = {pid: (lambda s: (s.safe_moves() or [s.dir])[0]) for pid in m["players"]}
    threads, results = run_bots(server, m["tokens"], decide)
    wait_connected(gm, m["match_id"], 4)
    gm.post(f"/matches/{m['match_id']}/start").raise_for_status()
    for t in threads:
        t.join(timeout=30)

    assert len(results) == 4
    summary = gm.get(f"/matches/{m['match_id']}").json()
    assert summary["status"] == "done"
    assert {r["id"] for r in summary["result"]["players"]} == {"a", "b", "c", "d"}
    assert sum(r["missed_ticks"] for r in summary["result"]["players"]) == 0
    assert all(r["placement"] >= 1 for r in summary["result"]["players"])


def test_silent_client_is_autopiloted(server, gm):
    m = new_match(gm, ["a", "b"], max_ticks=6)
    ws_url = server.replace("http", "ws")
    conns = [connect(f"{ws_url}/ws/play?token={t}") for t in m["tokens"].values()]
    for c in conns:
        json.loads(c.recv())  # welcome
    gm.post(f"/matches/{m['match_id']}/start").raise_for_status()

    # nobody sends a move: every tick is a missed tick, match still completes
    deadline = 30
    while True:
        msg = json.loads(conns[0].recv(timeout=deadline))
        if msg["type"] == "match_end":
            break
    for c in conns:
        c.close()
    result = gm.get(f"/matches/{m['match_id']}").json()["result"]
    assert result["players"][0]["missed_ticks"] > 0
    assert all(r["reliability"] <= 0 for r in result["players"])


def test_reconnect_mid_match(server, gm):
    m = new_match(gm, ["a", "b"], max_ticks=12)
    ws_url = server.replace("http", "ws")
    tok_a, tok_b = m["tokens"]["a"], m["tokens"]["b"]
    a = connect(f"{ws_url}/ws/play?token={tok_a}")
    json.loads(a.recv())
    b_thread = threading.Thread(
        target=play, args=(server, tok_b, lambda s: (s.safe_moves() or [s.dir])[0])
    )
    b_thread.start()
    gm.post(f"/matches/{m['match_id']}/start").raise_for_status()

    json.loads(a.recv(timeout=10))  # one state, then rudely vanish
    a.close()
    a2 = connect(f"{ws_url}/ws/play?token={tok_a}")  # same token, new socket
    hello = json.loads(a2.recv(timeout=10))
    assert hello["type"] == "welcome" and hello["status"] in ("running", "done")
    while True:
        msg = json.loads(a2.recv(timeout=30))
        if msg["type"] == "state":
            a2.send(json.dumps({"v": 1, "type": "move", "match_id": m["match_id"],
                                "tick": msg["tick"], "move": (msg["you"]["dir"])}))
        if msg["type"] == "match_end":
            break
    a2.close()
    b_thread.join(timeout=30)
    assert gm.get(f"/matches/{m['match_id']}").json()["status"] == "done"


def test_jev_meters_and_cuts_off(server, gm):
    m = new_match(gm, ["a", "b"], max_ticks=200)
    token = m["tokens"]["a"]
    client = httpx.Client(base_url=server, headers={"player-token": token}, timeout=10)

    r = client.post("/jev", json={"prompt": "pick a move", "schema": "Move"})
    assert r.status_code == 200
    first = r.json()
    assert first["text"] in ("N", "E", "S", "W")  # mock returns a legal move
    assert first["tokens"] > 0

    meters = gm.get(f"/matches/{m['match_id']}").json()["meters"]
    mine = next(x for x in meters if x["id"] == "a")
    assert mine["tokens_used"] == first["tokens"] and mine["calls"] == 1

    # burn the budget, then expect 402
    match = _match(m["match_id"])
    match.spend("a", match.budget, 0, 0)
    assert client.post("/jev", json={"prompt": "again"}).status_code == 402
    assert httpx.post(f"{server}/jev", json={"prompt": "hi"},
                      headers={"player-token": "nope"}).status_code == 401


def test_sdk_jev_returns_none_when_broke(server, gm):
    m = new_match(gm, ["a", "b"], max_ticks=200)
    arena = Arena(server, m["tokens"]["a"], verbose=False)  # sets the module globals
    assert jev("give me a move", schema=Move) in ("N", "E", "S", "W")
    match = _match(m["match_id"])
    match.spend("a", match.budget, 0, 0)
    assert jev("give me a move", schema=Move) is None
    assert arena.result is None


def test_template_bot_survives_alone(server, gm):
    m = new_match(gm, ["solo"], max_ticks=60, w=30, h=30)

    def decide(state):
        safe = state.safe_moves()
        return (safe or [state.dir])[0]

    threads, results = run_bots(server, m["tokens"], {"solo": decide})
    wait_connected(gm, m["match_id"], 1)
    gm.post(f"/matches/{m['match_id']}/start").raise_for_status()
    for t in threads:
        t.join(timeout=60)
    assert results[0]["ticks_survived"] >= 50


def test_gm_endpoints_are_password_gated(server, gm):
    assert httpx.post(f"{server}/matches", json={"players": ["a"]}).status_code == 403
    assert gm.get("/leaderboard").status_code == 200


def _match(match_id):
    from server.matches import MATCHES

    return MATCHES[match_id]
