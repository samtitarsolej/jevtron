"""Baseline bot: zero Jev calls. Flood-fills and walks into the biggest room."""

import os

from jevtron_sdk import DELTA, Arena

arena = Arena(os.getenv("JEVTRON_SERVER", "http://localhost:8000"), os.getenv("PLAYER_TOKEN", ""))


def room(state, start):
    """How many cells are reachable from `start` (cheap flood fill)."""
    seen, stack = {start}, [start]
    while stack and len(seen) < 400:
        x, y = stack.pop()
        for dx, dy in DELTA.values():
            n = (x + dx, y + dy)
            if n not in seen and state.free(*n):
                seen.add(n)
                stack.append(n)
    return len(seen)


@arena.on_tick
def decide(state):
    safe = state.safe_moves()
    if not safe:
        return state.dir
    x, y = state.pos
    return max(safe, key=lambda m: room(state, (x + DELTA[m][0], y + DELTA[m][1])))


if __name__ == "__main__":
    arena.run()
