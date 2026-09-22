# Jev-Tron Arena — Rules

Tron light-cycles, turn-based, 4 bots per match. Last bike alive wins.

## The arena
- Grid 40×40 (`config.yaml`), origin top-left, `x` right, `y` down.
- Every bot leaves a solid trail behind it. Trails never disappear — dead bots' trails stay as walls.
- Moves are `N`, `E`, `S`, `W`. All 4 bots move **simultaneously**.

## Dying
You die when your next cell is:
- outside the arena (or inside a shrunken border),
- any trail, including your own,
- the same cell another bot moves into that tick (head-on = both die).

## Turns
- Each tick the server sends you the state and waits `deadline_ms` (default 3000 ms).
- No move in time → **autopilot**: you keep your current direction, and it is logged as a missed tick.
- A 180° reversal is not a move — it is read as "carry straight on".
- The match ends when ≤1 bot is alive or at `max_ticks` (default 400).

## The brain
- The only allowed AI is **Jev**, called through the server proxy (`jev()` in the SDK).
- Every call is metered: prompt + completion tokens, per tick.
- Budget per match: 20 000 tokens. At 0 the proxy answers `402` and `jev()` returns `None` — you play on without a brain.
- Hard cap of 300 tokens per call. No calling other models; the proxy is the only route out.

## Scoring (per match, then summed over the tournament)
| placement | 1st | 2nd | 3rd | 4th |
|---|---|---|---|---|
| points | 4 | 2 | 1 | 0 |

- `performance = placement_points + ticks_survived / max_ticks`
- `efficiency  = placement_points / max(tokens_used, 1) * 1000`
- `reliability = 1 - missed_ticks / ticks_survived`
- `score = 0.5·norm(performance) + 0.3·norm(efficiency) + 0.1·norm(reliability) + 0.1·style_bonus`

`norm()` is min-max across the 4 players in that match (all-tied → 0.5). `style_bonus` (0–1) is set by the GM.

Winning cheaply beats winning expensively. Surviving without answering does not count as reliable.

## Curveballs
The GM can flip these on, mid-match, without warning:
- **fog** — you only see cells within `fog_radius` of your head; everything else is `?`.
- **shrink** — the border eats a ring every `shrink_every` ticks.
- **bonus tiles** — `*` cells; driving over one is worth style points.

## Not allowed
- Any brain other than Jev via the proxy.
- More than one process per `player_token` (reconnects are fine, one socket at a time).
