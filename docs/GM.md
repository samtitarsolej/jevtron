# GM run-of-show

## Before the hackathon
```bash
npm run setup        # venv + deps + SDK + node modules
npx turbo test       # everything green
npm run dryrun       # 3-round tournament, mock Jev, unattended
```
One command for the room: `SERVER_PORT=8001 npx turbo dev` runs server and spectator together.
Set the real brain: `export JEV_API_KEY=... JEV_BASE_URL=...` (leave `JEV_MOCK` unset).

## Two servers
| | command | budget | scoring |
|---|---|---|---|
| clone (practice) | `docker compose up clone` (:8000) | unlimited | off |
| production | `docker compose up prod` (:8001) | 20 000/match | on |

Spectator: `docker compose up spectator` → http://localhost:3000 (`NEXT_PUBLIC_SERVER` points it at a server).
GM password: `GM_PASSWORD` env, default `jev`. Everything below needs header `x-gm-password`.

## What to send each contestant
The spectator's **GM** tab generates this per player — hit **invite**, paste into their DM:

```
Jev-Tron Arena — you are "alice"

Server : http://10.51.10.128:8000
Token  : 3fa2c1d0-alice
Match  : 3fa2c1d0

git clone <repo> && cd jevtron
python3 -m venv .venv && . .venv/bin/activate && pip install -e ./sdk
PLAYER_TOKEN=3fa2c1d0-alice JEVTRON_SERVER=http://10.51.10.128:8000 python sdk/bot_template.py

Then copy sdk/bot_template.py to my_bot.py and make it yours.

Rules: docs/RULES.md · SDK: docs/SDK.md
Budget: 20000 tokens/match · Turn deadline: 3000 ms
```

Four things they actually need: **repo · server URL · their token · RULES.md**.
The server URL uses the LAN IP the server reports in `/health` — not `localhost`.
Tokens are `<match_id>-<player_id>` and are per match, so every new match means new invites
(**copy all** gives you all four at once).

## Running a match
```bash
# 1. create (returns a player_token per contestant — hand them out)
curl -XPOST localhost:8001/matches -H 'x-gm-password: jev' -H 'content-type: application/json' \
     -d '{"players":["alice","bob","cid","dee"]}'

# 2. wait until the spectator shows all four connected, then
curl -XPOST localhost:8001/matches/<id>/start -H 'x-gm-password: jev'
```
Or a whole tournament: `POST /tournament {"players":[...], "rounds":3}` — seating rotates each round.

Easier: the spectator's **GM** tab does all of it — create match or tournament, watch the
`3/4 connected` counter, start, fire curveballs, copy invites, set style bonuses. Password and
player list are remembered in the browser.

## Curveballs (mid-match, live)
```bash
curl -XPOST localhost:8001/matches/<id>/curveball -H 'x-gm-password: jev' \
     -H 'content-type: application/json' -d '{"fog_radius":5}'
```
| curveball | body | effect |
|---|---|---|
| fog | `{"fog_radius":5}` | bots only see 5 cells around their head |
| shrink | `{"shrink_every":20}` | border eats a ring every 20 ticks |
| bonus tiles | `{"bonus_tiles":5}` | drops 5 `*` tiles on free cells |
Turn one off again with `null` / `0`.

## Scoring knobs
- `POST /players/<id>/style_bonus {"value":0.8}` — your 10%, judged by eye.
- `GET /leaderboard` — running totals across scored matches.
- Weights live in `server/config.yaml`; changing them mid-tournament rewrites history, so don't.

## Replays
- `replays/<match_id>.json` — every tick, every move, running token totals.
- `GET /replays` / `GET /replays/<id>`, or the spectator's **Replay** tab (scrubbable).

## Known sharp edges
- A bot that never calls Jev maxes the efficiency term (30%). If that is not the game you want, raise the performance weight before round 1 and tell everyone.
- No sandbox: contestant scripts run on their own machines, trust + the proxy log is the only detection.
- State is in memory. Restarting the server loses the leaderboard; replays survive.
