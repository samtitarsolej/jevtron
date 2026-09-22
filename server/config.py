"""config.yaml + a couple of env switches. No settings class, no layering."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

PATH = Path(os.getenv("JEVTRON_CONFIG", Path(__file__).with_name("config.yaml")))
CONFIG: dict = yaml.safe_load(PATH.read_text())

MODE = os.getenv("MODE", "clone")  # "clone" = free play, "prod" = budget + scoring
GM_PASSWORD = os.getenv("GM_PASSWORD", "jev")
REPLAY_DIR = Path(os.getenv("REPLAY_DIR", Path(__file__).parent.parent / "replays"))


def scored() -> bool:
    return MODE == "prod"


def budget() -> int:
    return CONFIG["token_budget"] if scored() else 10**9
