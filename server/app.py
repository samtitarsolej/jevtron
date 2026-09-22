"""FastAPI app: GM REST + the ws and jev routers. `uvicorn server.app:app`."""

from __future__ import annotations

import asyncio
import json
import random

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server import config, jev, matches, ws

app = FastAPI(title="Jev-Tron Arena")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(jev.router)
app.include_router(ws.router)

TASKS: dict[str, asyncio.Task] = {}


def gm(x_gm_password: str = Header("")) -> None:
    if x_gm_password != config.GM_PASSWORD:
        raise HTTPException(403, "GM only")


class NewMatch(BaseModel):
    players: list[str]
    seed: int | None = None
    w: int | None = None
    h: int | None = None
    max_ticks: int | None = None
    deadline_ms: int | None = None
    fog_radius: int | None = None
    shrink_every: int | None = None
    bonus_tiles: int | None = None


class NewTournament(NewMatch):
    rounds: int = 3


class Curveball(BaseModel):
    fog_radius: int | None = None
    shrink_every: int | None = None
    bonus_tiles: int | None = None


class StyleBonus(BaseModel):
    value: float


def _summary(m: matches.Match) -> dict:
    return {
        "match_id": m.id,
        "status": m.status,
        "players": m.player_ids,
        "tick": m.state.tick,
        "config": vars(m.cfg),
        "meters": m.meters(),
        "result": m.result,
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mode": config.MODE, "jev_mock": jev.MOCK, "matches": len(matches.MATCHES)}


@app.post("/matches", dependencies=[Depends(gm)])
def create_match(body: NewMatch) -> dict:
    d = body.model_dump()
    m = matches.create_match(d.pop("players"), **d)
    return {**_summary(m), "tokens": matches.tokens_for(m)}


@app.post("/tournament", dependencies=[Depends(gm)])
def create_tournament(body: NewTournament) -> dict:
    d = body.model_dump()
    ms = matches.make_tournament(d.pop("players"), rounds=d.pop("rounds"), **d)
    return {"matches": [{**_summary(m), "tokens": matches.tokens_for(m)} for m in ms]}


@app.get("/matches")
def list_matches() -> dict:
    return {"matches": [_summary(m) for m in matches.MATCHES.values()]}


@app.get("/matches/{match_id}")
def get_match(match_id: str) -> dict:
    return _summary(_find(match_id))


@app.post("/matches/{match_id}/start", dependencies=[Depends(gm)])
async def start_match(match_id: str) -> dict:
    m = _find(match_id)
    if m.status != "lobby":
        raise HTTPException(409, f"match is {m.status}")
    TASKS[m.id] = asyncio.create_task(m.run())
    return _summary(m)


@app.post("/matches/{match_id}/curveball", dependencies=[Depends(gm)])
async def curveball(match_id: str, body: Curveball) -> dict:
    m = _find(match_id)
    for k, v in body.model_dump().items():
        if v is not None:
            setattr(m.cfg, k, v)  # live: the running state shares this Config
    if body.bonus_tiles:
        free = [
            (x, y)
            for x in range(m.cfg.w)
            for y in range(m.cfg.h)
            if (x, y) not in m.state.occupied() and not m.state.blocked_by_border((x, y))
        ]
        m.state.bonuses.update(random.sample(free, min(body.bonus_tiles, len(free))))
    return _summary(m)


@app.post("/players/{player_id}/style_bonus", dependencies=[Depends(gm)])
def style_bonus(player_id: str, body: StyleBonus) -> dict:
    matches.STYLE_BONUS[player_id] = max(0.0, min(1.0, body.value))
    return {"player_id": player_id, "style_bonus": matches.STYLE_BONUS[player_id]}


@app.get("/leaderboard")
def leaderboard() -> dict:
    rows = [
        {"id": pid, "score": round(s, 4), "style_bonus": matches.STYLE_BONUS.get(pid, 0.0)}
        for pid, s in matches.LEADERBOARD.items()
    ]
    return {"mode": config.MODE, "leaderboard": sorted(rows, key=lambda r: -r["score"])}


@app.get("/replays")
def list_replays() -> dict:
    config.REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    return {"replays": sorted(p.stem for p in config.REPLAY_DIR.glob("*.json"))}


@app.get("/replays/{match_id}")
def get_replay(match_id: str) -> dict:
    path = config.REPLAY_DIR / f"{match_id}.json"
    if not path.exists():
        raise HTTPException(404, "no such replay")
    return json.loads(path.read_text())


def _find(match_id: str) -> matches.Match:
    m = matches.MATCHES.get(match_id)
    if m is None:
        raise HTTPException(404, "no such match")
    return m
