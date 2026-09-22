"""Jev proxy + metering. The only route to a brain; tokens are counted here."""

from __future__ import annotations

import os
import random
import time

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from server import config, engine
from server.matches import MATCHES, TOKENS

router = APIRouter()

MOCK = os.getenv("JEV_MOCK", "0") == "1"
BASE_URL = os.getenv("JEV_BASE_URL", "https://api.typesafe.ai/v1/jev")
API_KEY = os.getenv("JEV_API_KEY", "")


class JevRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str
    schema_: str | dict | None = Field(default=None, alias="schema")  # "schema" is a BaseModel attr
    max_tokens: int | None = None


class JevResponse(BaseModel):
    text: str
    tokens: int
    budget_left: int
    latency_ms: int


def _estimate(text: str) -> int:
    return max(1, len(text) // 4)  # ponytail: only used when upstream omits usage


def _mock(match, pid: str) -> str:
    """A random legal move, so dry runs and tests need no upstream."""
    p = match.state.player(pid)
    safe = [
        m
        for m in engine.MOVES
        if m != engine.OPPOSITE[p.dir]
        and not match.state.blocked((p.pos[0] + engine.DELTA[m][0], p.pos[1] + engine.DELTA[m][1]))
    ]
    return random.choice(safe or [p.dir])


@router.post("/jev", response_model=JevResponse)
async def jev(req: JevRequest, player_token: str = Header(...)) -> JevResponse:
    if player_token not in TOKENS:
        raise HTTPException(401, "unknown player_token")
    match_id, pid = TOKENS[player_token]
    match = MATCHES[match_id]
    if match.budget_left(pid) <= 0:
        raise HTTPException(402, "token budget exhausted")

    cap = min(req.max_tokens or config.CONFIG["jev_max_tokens"], config.CONFIG["jev_max_tokens"])
    t0 = time.monotonic()
    if MOCK:
        text = _mock(match, pid)
        prompt_tokens, completion_tokens = _estimate(req.prompt), _estimate(text)
    else:
        # ponytail: generic JSON shape; adjust the two field names if Jev's API differs.
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                BASE_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={"prompt": req.prompt, "schema": req.schema_, "max_tokens": cap},
            )
        if r.status_code >= 400:
            raise HTTPException(502, f"jev upstream {r.status_code}: {r.text[:200]}")
        data = r.json()
        text = str(data.get("output") or data.get("text") or data.get("content") or "")
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens", _estimate(req.prompt))
        completion_tokens = usage.get("completion_tokens", _estimate(text))
    latency_ms = int((time.monotonic() - t0) * 1000)

    match.spend(pid, prompt_tokens, completion_tokens, latency_ms)
    return JevResponse(
        text=text,
        tokens=prompt_tokens + completion_tokens,
        budget_left=match.budget_left(pid),
        latency_ms=latency_ms,
    )
