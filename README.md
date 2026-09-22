# Jev-Tron Arena

Turn-based Tron for an internal hackathon. One GM server, four contestant bots,
one allowed brain: **Jev**, via a metered server-side proxy.

```bash
make install     # venv + deps + SDK
make test        # engine, ws, proxy, sdk
make sim         # 4 random bots in ASCII, no server
make dryrun      # prod server + mock Jev + 3-round tournament + leaderboard
make clone       # free-play server on :8000     (MODE=clone)
make prod        # scored server on :8000        (MODE=prod)
make spectator   # live view on :3000
```

- `server/` — engine (pure), ws tick loop, Jev proxy + metering, matches/scoring
- `sdk/` — `pip install -e ./sdk`, plus `bot_template.py` and `bot_greedy.py`
- `spectator/` — Next.js live arena, leaderboard, replay scrubber, GM drawer
- `docs/` — [RULES](docs/RULES.md) (contestants) · [SDK](docs/SDK.md) · [GM](docs/GM.md)
