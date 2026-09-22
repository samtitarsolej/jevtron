"""Starter bot: safe moves + one Jev call per tick. Copy me and get weird.

    PLAYER_TOKEN=... python bot_template.py
"""

import os

from jevtron_sdk import Arena, Move, jev

arena = Arena(os.getenv("JEVTRON_SERVER", "http://localhost:8000"), os.getenv("PLAYER_TOKEN", ""))


@arena.on_tick
def decide(state):
    safe = state.safe_moves()
    if len(safe) <= 1:
        return (safe or [state.dir])[0]  # no choice = no reason to pay for one

    prompt = (
        f"Tron arena, you are '{state.raw['you']['id']}' at {state.pos} heading {state.dir}.\n"
        f"{state.ascii()}\n"
        f"Letters A-D are heads, digits are their trails, # wall, * bonus, ? unknown.\n"
        f"Safe moves right now: {', '.join(safe)} "
        f"(open cells ahead: {[state.distance_to_wall(m) for m in safe]}).\n"
        "Pick the move that keeps the most room. Answer with one letter."
    )
    move = jev(prompt, schema=Move, max_tokens=4)
    return move if move in safe else safe[0]


if __name__ == "__main__":
    arena.run()
