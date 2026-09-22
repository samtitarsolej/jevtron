# Jev-Tron Arena

Turn-based Tron for an internal hackathon. One GM server, four contestant bots,
one allowed brain: **Jev**, via a metered server-side proxy.

Turborepo monorepo (npm workspaces). `make` targets are aliases for the same tasks.

```bash
npm run setup      # venv + python deps + SDK + node deps   (= make install)
npx turbo test     # engine, ws, proxy, sdk                 (= make test)
npx turbo dev      # clone server + spectator, in parallel  (= make dev)
npx turbo build    # spectator build, cached                (= make build)
npm run sim        # 4 random bots in ASCII, no server
npm run dryrun     # prod server + mock Jev + 3-round tournament + leaderboard
npm run clone      # free-play server  (MODE=clone)
npm run prod       # scored server     (MODE=prod)
```

Ports: `SERVER_PORT` (default 8000) and `SPECTATOR_PORT` (default 3000). Point the
UI at a server with `NEXT_PUBLIC_SERVER`.

- `server/` — engine (pure), ws tick loop, Jev proxy + metering, matches/scoring
  (its `package.json` is a task shim; the code is Python, run from `.venv`)
- `sdk/` — `pip install -e ./sdk`, plus `bot_template.py` and `bot_greedy.py`
- `spectator/` — Next.js live arena, leaderboard, replay scrubber, GM drawer
- `docs/` — [RULES](docs/RULES.md) (contestants) · [SDK](docs/SDK.md) · [GM](docs/GM.md)
