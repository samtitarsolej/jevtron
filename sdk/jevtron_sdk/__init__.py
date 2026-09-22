"""Jev-Tron contestant SDK.

    from jevtron_sdk import Arena, jev, Move

    arena = Arena(server_url, player_token)

    @arena.on_tick
    def decide(state) -> Move:
        r = jev(f"{state.ascii()}\\nYou are A. Reply N/E/S/W.", schema=Move)
        return r or state.safe_moves()[0]

    arena.run()
"""

from __future__ import annotations

import json
import traceback
import typing
from dataclasses import dataclass
from typing import Callable, Literal

import httpx
from websockets.sync.client import connect

__all__ = ["Arena", "jev", "Move", "State", "MOVES"]

Move = Literal["N", "E", "S", "W"]
MOVES: tuple[str, ...] = ("N", "E", "S", "W")
DELTA = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
FREE = ".*?"  # "?" is fogged: unknown, so optimistically walkable

_SERVER = ""
_TOKEN = ""
last_call: dict = {}  # tokens/latency of the most recent jev() call


@dataclass
class State:
    """One tick as your bot sees it."""

    raw: dict

    @property
    def tick(self) -> int:
        return self.raw["tick"]

    @property
    def grid(self) -> list[str]:
        return self.raw["grid_view"]

    @property
    def pos(self) -> tuple[int, int]:
        return tuple(self.raw["you"]["pos"])  # type: ignore[return-value]

    @property
    def dir(self) -> str:
        return self.raw["you"]["dir"]

    @property
    def alive(self) -> bool:
        return self.raw["you"]["alive"]

    @property
    def budget_left(self) -> int:
        return self.raw["budget_left"]

    @property
    def players(self) -> list[dict]:
        return self.raw["players"]

    def cell(self, x: int, y: int) -> str:
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[0]):
            return self.grid[y][x]
        return "#"

    def free(self, x: int, y: int) -> bool:
        return self.cell(x, y) in FREE

    def safe_moves(self) -> list[Move]:
        """Moves that don't kill you next tick, longest runway first."""
        x, y = self.pos
        ok = [
            m
            for m in MOVES
            if m != OPPOSITE[self.dir] and self.free(x + DELTA[m][0], y + DELTA[m][1])
        ]
        return sorted(ok, key=lambda m: -self.distance_to_wall(m))  # type: ignore[return-value]

    def distance_to_wall(self, direction: str) -> int:
        """Free cells straight ahead in `direction`."""
        x, y = self.pos
        dx, dy = DELTA[direction]
        n = 0
        while self.free(x + dx * (n + 1), y + dy * (n + 1)):
            n += 1
        return n

    def ascii(self) -> str:
        return "\n".join(self.grid)


def _coerce(text: str, schema):
    if schema is None:
        return text
    if typing.get_origin(schema) is Literal:
        allowed = typing.get_args(schema)
        up = text.upper()
        return next((a for a in allowed if a in up), None)
    if hasattr(schema, "model_validate_json"):  # pydantic model
        try:
            return schema.model_validate_json(text)
        except Exception:
            return None
    try:
        return json.loads(text)
    except Exception:
        return None


def jev(prompt: str, schema=None, max_tokens: int | None = None, timeout: float = 20.0):
    """Ask Jev through the arena proxy. None = out of budget, timeout or junk."""
    global last_call
    body: dict = {"prompt": prompt}
    if schema is not None:
        body["schema"] = getattr(schema, "__name__", str(schema))
    if max_tokens:
        body["max_tokens"] = max_tokens
    try:
        r = httpx.post(
            f"{_SERVER}/jev", json=body, headers={"player-token": _TOKEN}, timeout=timeout
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None  # 402 = budget gone; play on without a brain
    data = r.json()
    last_call = {k: data[k] for k in ("tokens", "budget_left", "latency_ms")}
    return _coerce(data["text"], schema)


class Arena:
    def __init__(self, server_url: str, player_token: str, verbose: bool = True):
        global _SERVER, _TOKEN
        self.http = server_url.rstrip("/")
        _SERVER, _TOKEN = self.http, player_token
        self.token = player_token
        self.verbose = verbose
        self.decide: Callable[[State], str] | None = None
        self.result: dict | None = None

    def on_tick(self, fn: Callable[[State], str]) -> Callable[[State], str]:
        self.decide = fn
        return fn

    def _ws_url(self) -> str:
        base = self.http.replace("http://", "ws://").replace("https://", "wss://")
        return f"{base}/ws/play?token={self.token}"

    def run(self) -> dict | None:
        """Play one match. Returns the match_end payload."""
        assert self.decide, "decorate a function with @arena.on_tick first"
        with connect(self._ws_url(), max_size=4_000_000) as ws:
            for message in ws:
                msg = json.loads(message)
                if msg["type"] == "welcome" and self.verbose:
                    print(f"[jevtron] joined {msg['match_id']} as {msg['you']}")
                elif msg["type"] == "state":
                    state = State(msg)
                    if not state.alive:
                        continue
                    try:
                        move = self.decide(state)
                    except Exception:
                        traceback.print_exc()
                        move = None
                    if move not in MOVES:
                        move = (state.safe_moves() or [state.dir])[0]
                    ws.send(
                        json.dumps(
                            {
                                "v": 1,
                                "type": "move",
                                "match_id": msg["match_id"],
                                "tick": state.tick,
                                "move": move,
                            }
                        )
                    )
                elif msg["type"] == "match_end":
                    self.result = msg
                    if self.verbose:
                        print(
                            f"[jevtron] done: placement {msg['placement']}, "
                            f"{msg['ticks_survived']} ticks, {msg['tokens_used']} tokens, "
                            f"score {msg['score']:.3f}"
                        )
                    return msg
        return self.result
