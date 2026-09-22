"""`make sim` — 4 dumb bots, ASCII frames. Also the determinism fixture for tests."""

from __future__ import annotations

import random
import sys

from server import engine
from server.engine import Config, GameState, Move


def random_bot(state: GameState, pid: str, rng: random.Random) -> Move:
    """Pick a random move that is not instantly fatal; else go straight."""
    p = state.player(pid)
    safe = [
        m
        for m in engine.MOVES
        if m != engine.OPPOSITE[p.dir]
        and not state.blocked((p.pos[0] + engine.DELTA[m][0], p.pos[1] + engine.DELTA[m][1]))
    ]
    return rng.choice(safe) if safe else p.dir


def run(cfg: Config, n_players: int = 4) -> list[dict]:
    rng = random.Random(cfg.seed)
    state = engine.new_game(cfg, [f"p{i}" for i in range(n_players)])
    log = [engine.to_dict(state)]
    while not engine.is_finished(state):
        moves = {p.id: random_bot(state, p.id, rng) for p in state.alive()}
        state = engine.step(state, moves)
        log.append(engine.to_dict(state))
    return log


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cfg = Config(w=30, h=20, max_ticks=200, seed=seed)
    for frame in run(cfg):
        print("\033[2J\033[H", end="")  # clear
        print(f"tick {frame['tick']}  " + "  ".join(
            f"{p['id']}:{'alive' if p['alive'] else 'dead '}" for p in frame["players"]))
        print("\n".join(frame["grid"]))
    print("winner:", [p["id"] for p in frame["players"] if p["alive"]] or "nobody")
