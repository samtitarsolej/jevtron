# GM run-of-show

## Before the hackathon
```bash
make install
make test            # everything green
make dryrun          # 3-round tournament, mock Jev, unattended
```
Set the real brain: `export JEV_API_KEY=... JEV_BASE_URL=...` (leave `JEV_MOCK` unset).

## Two servers
| | command | budget | scoring |
|---|---|---|---|
| clone (practice) | `docker compose up clone` (:8000) | unlimited | off |
| production | `docker compose up prod` (:8001) | 20 000/match | on |

Spectator: `docker compose up spectator` → http://localhost:3000 (`NEXT_PUBLIC_SERVER` points it at a server).
GM password: `GM_PASSWORD` env, default `jev`. Everything below needs header `x-gm-password`.

## Running a match
```bash
# 1. create (returns a player_token per contestant — hand them out)
curl -XPOST localhost:8001/matches -H 'x-gm-password: jev' -H 'content-type: application/json' \
     -d '{"players":["alice","bob","cid","dee"]}'

# 2. wait until the spectator shows all four connected, then
curl -XPOST localhost:8001/matches/<id>/start -H 'x-gm-password: jev'
```
Or a whole tournament: `POST /tournament {"players":[...], "rounds":3}` — seating rotates each round.
The spectator's **GM** tab does all of this with buttons.

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
