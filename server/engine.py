"""Pure, deterministic Tron engine. No I/O, no imports from the rest of the server.

Rendering is ASCII on purpose: it is the same thing the SDK shows a bot, a bot
shows Jev, and the spectator draws. One representation, no converters.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Literal

Move = Literal["N", "E", "S", "W"]
MOVES: tuple[Move, ...] = ("N", "E", "S", "W")
DELTA: dict[Move, tuple[int, int]] = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
OPPOSITE: dict[Move, Move] = {"N": "S", "S": "N", "E": "W", "W": "E"}

HEADS = "ABCD"  # player i head glyph
TRAILS = "0123"  # player i trail glyph


@dataclass
class Config:
    w: int = 40
    h: int = 40
    max_ticks: int = 400
    seed: int = 0
    fog_radius: int | None = None
    shrink_every: int | None = None
    bonus_tiles: int = 0


@dataclass
class Player:
    id: str
    pos: tuple[int, int]
    dir: Move
    alive: bool = True
    trail: list[tuple[int, int]] = field(default_factory=list)
    died_tick: int | None = None
    bonus: int = 0


@dataclass
class GameState:
    cfg: Config
    players: list[Player]
    tick: int = 0
    walls: set[tuple[int, int]] = field(default_factory=set)
    bonuses: set[tuple[int, int]] = field(default_factory=set)
    shrink: int = 0  # rings eaten from the border

    # --- queries -------------------------------------------------------
    def player(self, pid: str) -> Player:
        return next(p for p in self.players if p.id == pid)

    def alive(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def occupied(self) -> set[tuple[int, int]]:
        cells = set(self.walls)
        for p in self.players:
            cells.update(p.trail)
        return cells

    def blocked_by_border(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return not (
            self.shrink <= x < self.cfg.w - self.shrink
            and self.shrink <= y < self.cfg.h - self.shrink
        )

    def blocked(self, cell: tuple[int, int]) -> bool:
        if self.blocked_by_border(cell) or cell in self.walls:
            return True
        return any(cell in p.trail for p in self.players)


def new_game(cfg: Config, player_ids: list[str]) -> GameState:
    """Spawn players on a symmetric ring, facing inward-ish."""
    w, h = cfg.w, cfg.h
    spawns: list[tuple[tuple[int, int], Move]] = [
        ((w // 4, h // 4), "S"),
        ((3 * w // 4, h // 4), "W"),
        ((3 * w // 4, 3 * h // 4), "N"),
        ((w // 4, 3 * h // 4), "E"),
    ]
    players = [
        Player(id=pid, pos=spawns[i % 4][0], dir=spawns[i % 4][1], trail=[spawns[i % 4][0]])
        for i, pid in enumerate(player_ids)
    ]
    state = GameState(cfg=cfg, players=players)
    if cfg.bonus_tiles:
        rng = random.Random(cfg.seed)
        taken = state.occupied()
        while len(state.bonuses) < cfg.bonus_tiles:
            cell = (rng.randrange(w), rng.randrange(h))
            if cell not in taken and cell not in state.bonuses:
                state.bonuses.add(cell)
    return state


def step(state: GameState, moves: dict[str, Move | None]) -> GameState:
    """Advance one tick. Missing/illegal move = keep going straight."""
    nxt = replace(
        state,
        tick=state.tick + 1,
        players=[replace(p, trail=list(p.trail)) for p in state.players],
        walls=set(state.walls),
        bonuses=set(state.bonuses),
    )

    if nxt.cfg.shrink_every and nxt.tick % nxt.cfg.shrink_every == 0:
        nxt.shrink += 1

    heads: dict[str, tuple[int, int]] = {}
    for p in nxt.players:
        if not p.alive:
            continue
        m = moves.get(p.id) or p.dir
        if m not in DELTA or m == OPPOSITE[p.dir]:
            m = p.dir  # no 180s; a reversal just means "carry on"
        p.dir = m
        dx, dy = DELTA[m]
        heads[p.id] = (p.pos[0] + dx, p.pos[1] + dy)

    dead: set[str] = set()
    for pid, cell in heads.items():
        if nxt.blocked(cell):
            dead.add(pid)
    for pid, cell in heads.items():  # head-on into the same cell kills both
        for other, ocell in heads.items():
            if other != pid and ocell == cell:
                dead.add(pid)
                dead.add(other)

    for p in nxt.players:
        if not p.alive:
            continue
        if p.id in dead:
            p.alive = False
            p.died_tick = nxt.tick
            continue
        p.pos = heads[p.id]
        p.trail.append(p.pos)
        if p.pos in nxt.bonuses:
            nxt.bonuses.discard(p.pos)
            p.bonus += 1

    # a shrink ring can also swallow someone standing still-ish
    for p in nxt.players:
        if p.alive and nxt.blocked_by_border(p.pos):
            p.alive = False
            p.died_tick = nxt.tick
    return nxt


def is_finished(state: GameState) -> bool:
    if state.tick >= state.cfg.max_ticks:
        return True
    # solo practice runs the clock out; a real match ends when one bike is left
    return len(state.alive()) <= (0 if len(state.players) == 1 else 1)


def render(state: GameState, fog_for: str | None = None) -> list[str]:
    """ASCII arena. `fog_for` hides everything outside that player's fog radius."""
    w, h = state.cfg.w, state.cfg.h
    grid = [["." for _ in range(w)] for _ in range(h)]
    for x in range(w):
        for y in range(h):
            if state.blocked_by_border((x, y)):
                grid[y][x] = "#"
    for cell in state.walls:
        grid[cell[1]][cell[0]] = "#"
    for cell in state.bonuses:
        grid[cell[1]][cell[0]] = "*"
    for i, p in enumerate(state.players):
        for cell in p.trail:
            grid[cell[1]][cell[0]] = TRAILS[i % 4]
        if p.alive:
            grid[p.pos[1]][p.pos[0]] = HEADS[i % 4]

    r = state.cfg.fog_radius
    if fog_for is not None and r:
        hx, hy = state.player(fog_for).pos
        for y in range(h):
            for x in range(w):
                if abs(x - hx) + abs(y - hy) > r:
                    grid[y][x] = "?"
    return ["".join(row) for row in grid]


def to_dict(state: GameState) -> dict:
    return {
        "tick": state.tick,
        "shrink": state.shrink,
        "bonuses": sorted(state.bonuses),
        "players": [
            {
                "id": p.id,
                "pos": list(p.pos),
                "dir": p.dir,
                "alive": p.alive,
                "died_tick": p.died_tick,
                "bonus": p.bonus,
                "trail_len": len(p.trail),
            }
            for p in state.players
        ],
        "grid": render(state),
    }
