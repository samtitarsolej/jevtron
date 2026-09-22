# Jev-Tron SDK — from clone to playing in 10 minutes

## 1. Install
```bash
git clone <repo> && cd jevtron
python3 -m venv .venv && . .venv/bin/activate
pip install -e ./sdk
```

## 2. Get your token
The GM hands you a `player_token` and a server URL (the **clone** server for practice).

## 3. Write a bot
```python
import os
from jevtron_sdk import Arena, jev, Move

arena = Arena(os.getenv("JEVTRON_SERVER", "http://localhost:8000"), os.environ["PLAYER_TOKEN"])

@arena.on_tick
def decide(state) -> Move:
    safe = state.safe_moves()
    if len(safe) <= 1:
        return (safe or [state.dir])[0]          # no choice, no tokens spent
    move = jev(f"{state.ascii()}\nYou are at {state.pos}. Safe: {safe}. One letter.",
               schema=Move, max_tokens=4)
    return move if move in safe else safe[0]

arena.run()
```
```bash
PLAYER_TOKEN=... JEVTRON_SERVER=http://gm-box:8000 python my_bot.py
```

Two bots ship with the SDK: `sdk/bot_template.py` (one Jev call per tick) and
`sdk/bot_greedy.py` (flood-fill, no Jev at all — your baseline to beat).

## 4. `state`
| thing | what you get |
|---|---|
| `state.tick` | current tick |
| `state.pos`, `state.dir`, `state.alive` | your bike |
| `state.grid` / `state.ascii()` | the arena as rows of text |
| `state.safe_moves()` | legal non-suicidal moves, most open runway first |
| `state.distance_to_wall("N")` | free cells straight ahead |
| `state.free(x, y)` | is that cell walkable |
| `state.budget_left` | tokens you have left this match |
| `state.players` | every bot's `alive`, `trail_len`, `tokens_used` |

Grid glyphs: `A`–`D` heads · `0`–`3` their trails · `#` wall · `*` bonus · `?` fogged · `.` empty.
You are the letter matching your index in `state.players`.

## 5. `jev()`
```python
jev(prompt, schema=None, max_tokens=None, timeout=20.0)
```
- Goes through the arena proxy. Returns `None` on 402 (budget gone), timeout or unparseable output — **always have a fallback**.
- `schema=Move` → returns `"N"|"E"|"S"|"W"` or `None`. A pydantic model → parsed model or `None`.
- `jevtron_sdk.last_call` holds `tokens`, `budget_left`, `latency_ms` of the last call.

## 6. Token economy
- A full 40×40 grid in the prompt costs roughly 450 tokens — about 40 calls and your 20 000 is gone.
- Cheaper: send only what matters (safe moves, distances, nearby enemies), cap `max_tokens`, and skip the call when the move is forced.
- Efficiency is 30% of your score. A dead bot with a full wallet scores nothing either.

## 7. Reliability
- Answer before `deadline_ms` or you get autopiloted and lose reliability points.
- Your `decide()` raising is not fatal — the SDK falls back to a safe move — but keep the exception out of the hot path.
- Dropped connection? Reconnect with the same token; you rejoin the running match.
