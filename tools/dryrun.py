"""make dryrun — prod server + mock Jev + a full tournament, unattended.

Runs the real server in-process and the real SDK over real websockets; only the
Jev upstream is mocked. Prints the leaderboard at the end.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time

os.environ.setdefault("MODE", "prod")
os.environ.setdefault("JEV_MOCK", "1")
os.environ.setdefault("GM_PASSWORD", "dryrun")

import httpx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "sdk")]
import bot_greedy  # noqa: E402
import bot_template  # noqa: E402

from jevtron_sdk import Arena  # noqa: E402

BOTS = {"jev-alice": bot_template.decide, "jev-bob": bot_template.decide,
        "greedy-cid": bot_greedy.decide, "greedy-dee": bot_greedy.decide}


def start_server() -> str:
    import uvicorn

    from server.app import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(f"{url}/health", timeout=0.2)
            return url
        except Exception:
            time.sleep(0.05)
    raise SystemExit("server never came up")


def play_match(url: str, gm: httpx.Client, match: dict) -> None:
    threads = []
    for pid, token in match["tokens"].items():
        def run(pid=pid, token=token):
            arena = Arena(url, token, verbose=False)
            arena.on_tick(BOTS[pid])
            arena.run()

        t = threading.Thread(target=run)
        t.start()
        threads.append(t)

    for _ in range(200):  # wait for everyone to be on the grid
        meters = gm.get(f"/matches/{match['match_id']}").json()["meters"]
        if all(x["connected"] for x in meters):
            break
        time.sleep(0.05)
    gm.post(f"/matches/{match['match_id']}/start").raise_for_status()
    for t in threads:
        t.join(timeout=300)

    res = gm.get(f"/matches/{match['match_id']}").json()["result"]
    print(f"\nmatch {match['match_id']}  winner: {', '.join(res['winner']) or 'nobody'}")
    print(f"  {'player':12} {'place':>5} {'ticks':>6} {'tokens':>7} {'missed':>7} {'score':>6}")
    for r in sorted(res["players"], key=lambda r: r["placement"]):
        print(f"  {r['id']:12} {r['placement']:>5} {r['ticks_survived']:>6} "
              f"{r['tokens_used']:>7} {r['missed_ticks']:>7} {r['score']:>6.3f}")


def main() -> None:
    rounds = int(os.getenv("ROUNDS", "3"))
    url = start_server()
    gm = httpx.Client(base_url=url, headers={"x-gm-password": os.environ["GM_PASSWORD"]}, timeout=30)
    r = gm.post("/tournament", json={"players": list(BOTS), "rounds": rounds,
                                     "deadline_ms": 1000, "max_ticks": 200})
    r.raise_for_status()
    for match in r.json()["matches"]:
        play_match(url, gm, match)

    print("\n=== leaderboard ===")
    for row in gm.get("/leaderboard").json()["leaderboard"]:
        print(f"  {row['id']:12} {row['score']:>7.3f}")


if __name__ == "__main__":
    main()
