"""Match lifecycle: lobby, tick loop, metering, scoring, replay, leaderboard.

Everything lives in process memory; replays on disk are the only persistence
(non-goal in the plan). MATCHES/TOKENS are module globals because there is
exactly one server.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from server import config, engine
from server.engine import Config, Move

PROTOCOL = 1
PLACEMENT_POINTS = {1: 4, 2: 2, 3: 1, 4: 0}

MATCHES: dict[str, "Match"] = {}
TOKENS: dict[str, tuple[str, str]] = {}  # player_token -> (match_id, player_id)
STYLE_BONUS: dict[str, float] = {}  # player_id -> 0..1, set by the GM
LEADERBOARD: dict[str, float] = {}  # player_id -> summed score


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    last_latency_ms: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class Match:
    id: str
    cfg: Config
    player_ids: list[str]
    budget: int = field(default_factory=config.budget)
    deadline_ms: int = field(default_factory=lambda: config.CONFIG["deadline_ms"])
    status: str = "lobby"  # lobby -> running -> done
    state: engine.GameState = field(init=False)
    conns: dict[str, Any] = field(default_factory=dict)
    spectators: set = field(default_factory=set)
    moves: dict[str, Move] = field(default_factory=dict)
    usage: dict[str, Usage] = field(default_factory=dict)
    missed: dict[str, int] = field(default_factory=dict)
    log: list[dict] = field(default_factory=list)
    result: dict | None = None

    def __post_init__(self):
        self.state = engine.new_game(self.cfg, self.player_ids)
        self.usage = {pid: Usage() for pid in self.player_ids}
        self.missed = {pid: 0 for pid in self.player_ids}
        self._all_in = asyncio.Event()

    # --- metering ------------------------------------------------------
    def budget_left(self, pid: str) -> int:
        return self.budget - self.usage[pid].total

    def spend(self, pid: str, prompt: int, completion: int, latency_ms: int) -> None:
        u = self.usage[pid]
        u.calls += 1
        u.prompt_tokens += prompt
        u.completion_tokens += completion
        u.last_latency_ms = latency_ms

    # --- messaging -----------------------------------------------------
    def meters(self) -> list[dict]:
        return [
            {
                "id": pid,
                "tokens_used": self.usage[pid].total,
                "budget": self.budget,
                "calls": self.usage[pid].calls,
                "last_latency_ms": self.usage[pid].last_latency_ms,
                "missed_ticks": self.missed[pid],
                "connected": pid in self.conns,
            }
            for pid in self.player_ids
        ]

    def state_msg(self, pid: str) -> dict:
        me = self.state.player(pid)
        return {
            "v": PROTOCOL,
            "type": "state",
            "match_id": self.id,
            "tick": self.state.tick,
            "you": {"id": pid, "pos": list(me.pos), "dir": me.dir, "alive": me.alive},
            "grid_view": engine.render(self.state, fog_for=pid),
            "players": [
                {
                    "id": p.id,
                    "alive": p.alive,
                    "trail_len": len(p.trail),
                    "bonus": p.bonus,
                    "tokens_used": self.usage[p.id].total,
                }
                for p in self.state.players
            ],
            "budget_left": self.budget_left(pid),
            "deadline_ms": self.deadline_ms,
        }

    async def _send(self, ws, msg: dict) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            pass  # ponytail: a dropped socket is just autopilot; reader task cleans up

    async def broadcast(self) -> None:
        await asyncio.gather(*(self._send(ws, self.state_msg(pid)) for pid, ws in list(self.conns.items())))
        spec = {
            "v": PROTOCOL,
            "type": "spectate",
            "match_id": self.id,
            "status": self.status,
            "state": engine.to_dict(self.state),
            "meters": self.meters(),
            "result": self.result,
        }
        await asyncio.gather(*(self._send(ws, spec) for ws in list(self.spectators)))

    # --- move intake ---------------------------------------------------
    def submit(self, pid: str, tick: int, move: str) -> bool:
        """True if the move counted. Wrong tick or junk = ignored = missed tick."""
        if self.status != "running" or tick != self.state.tick or move not in engine.MOVES:
            return False
        if not self.state.player(pid).alive:
            return False
        self.moves[pid] = move  # type: ignore[assignment]
        self._check_all_in()
        return True

    def _check_all_in(self) -> None:
        waiting = [p.id for p in self.state.alive() if p.id in self.conns and p.id not in self.moves]
        if not waiting:
            self._all_in.set()

    # --- loop ----------------------------------------------------------
    async def run(self) -> dict:
        self.status = "running"
        self.log.append({"tick": self.state.tick, "state": engine.to_dict(self.state), "moves": {}})
        while not engine.is_finished(self.state):
            self.moves.clear()
            self._all_in.clear()
            await self.broadcast()
            self._check_all_in()
            try:
                await asyncio.wait_for(self._all_in.wait(), self.deadline_ms / 1000)
            except TimeoutError:
                pass
            moves = dict(self.moves)
            for p in self.state.alive():
                if p.id not in moves:
                    self.missed[p.id] += 1
            self.state = engine.step(self.state, moves)
            self.log.append(
                {
                    "tick": self.state.tick,
                    "state": engine.to_dict(self.state),
                    "moves": moves,
                    "tokens": {pid: self.usage[pid].total for pid in self.player_ids},
                }
            )
        return await self.finish()

    async def finish(self) -> dict:
        self.status = "done"
        self.result = score_match(self)
        await self.broadcast()
        for pid, ws in list(self.conns.items()):
            row = next(r for r in self.result["players"] if r["id"] == pid)
            await self._send(ws, {"v": PROTOCOL, "type": "match_end", **row})
        if config.scored():
            for row in self.result["players"]:
                LEADERBOARD[row["id"]] = LEADERBOARD.get(row["id"], 0.0) + row["score"]
        write_replay(self)
        return self.result


# --- scoring -----------------------------------------------------------


def _norm(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)  # ponytail: everyone tied -> neutral, not a free 1.0
    return [(v - lo) / (hi - lo) for v in values]


def score_match(m: Match) -> dict:
    max_ticks = m.cfg.max_ticks
    survived = {
        p.id: (p.died_tick if p.died_tick is not None else m.state.tick) for p in m.state.players
    }
    # placement: longer survival = better; ties share a placement (1,1,3,4)
    placement = {
        pid: 1 + sum(1 for o in survived.values() if o > t) for pid, t in survived.items()
    }
    points = {pid: PLACEMENT_POINTS.get(pl, 0) for pid, pl in placement.items()}

    ids = m.player_ids
    perf = [points[i] + survived[i] / max_ticks for i in ids]
    eff = [points[i] / max(m.usage[i].total, 1) * 1000 for i in ids]
    rel = [1 - m.missed[i] / max(survived[i], 1) for i in ids]
    style = [STYLE_BONUS.get(i, 0.0) for i in ids]

    w = config.CONFIG["scoring"]
    n_perf, n_eff, n_rel = _norm(perf), _norm(eff), _norm(rel)
    rows = []
    for k, pid in enumerate(ids):
        rows.append(
            {
                "id": pid,
                "placement": placement[pid],
                "ticks_survived": survived[pid],
                "tokens_used": m.usage[pid].total,
                "jev_calls": m.usage[pid].calls,
                "missed_ticks": m.missed[pid],
                "performance": perf[k],
                "efficiency": eff[k],
                "reliability": rel[k],
                "style_bonus": style[k],
                "score": (
                    w["performance"] * n_perf[k]
                    + w["efficiency"] * n_eff[k]
                    + w["reliability"] * n_rel[k]
                    + w["style"] * style[k]
                ),
            }
        )
    return {"match_id": m.id, "winner": [p.id for p in m.state.alive()], "players": rows}


def write_replay(m: Match) -> str:
    config.REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    path = config.REPLAY_DIR / f"{m.id}.json"
    path.write_text(
        json.dumps(
            {
                "match_id": m.id,
                "created": time.time(),
                "config": vars(m.cfg),
                "players": m.player_ids,
                "ticks": m.log,
                "result": m.result,
            }
        )
    )
    return str(path)


# --- lobby / tournament ------------------------------------------------


def create_match(player_ids: list[str], deadline_ms: int | None = None, **cfg_overrides) -> Match:
    c = config.CONFIG
    cfg = Config(
        w=c["grid"]["w"],
        h=c["grid"]["h"],
        max_ticks=c["max_ticks"],
        seed=cfg_overrides.pop("seed", None) or len(MATCHES) + 1,  # explicit null = auto-seed
        fog_radius=c["curveballs"]["fog_radius"],
        shrink_every=c["curveballs"]["shrink_every"],
        bonus_tiles=c["curveballs"]["bonus_tiles"],
    )
    for k, v in cfg_overrides.items():
        if v is not None and hasattr(cfg, k):
            setattr(cfg, k, v)
    m = Match(
        id=uuid.uuid4().hex[:8],
        cfg=cfg,
        player_ids=list(player_ids),
        deadline_ms=deadline_ms or c["deadline_ms"],
    )
    MATCHES[m.id] = m
    for pid in player_ids:
        TOKENS[f"{m.id}-{pid}"] = (m.id, pid)
    return m


def tokens_for(m: Match) -> dict[str, str]:
    return {pid: f"{m.id}-{pid}" for pid in m.player_ids}


def make_tournament(player_ids: list[str], rounds: int = 3, **cfg) -> list[Match]:
    """Rotate the seating each match so nobody is stuck on one spawn."""
    from itertools import combinations

    groups = [list(g) for g in combinations(player_ids, 4)] or [list(player_ids)]
    out = []
    for r in range(rounds):
        for g in groups:
            out.append(create_match(g[r % len(g):] + g[: r % len(g)], **cfg))
    return out
