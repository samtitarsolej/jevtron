import os
import socket
import threading
import time

import httpx
import pytest

os.environ.setdefault("MODE", "prod")
os.environ.setdefault("JEV_MOCK", "1")
os.environ.setdefault("GM_PASSWORD", "test")
os.environ.setdefault("REPLAY_DIR", "/tmp/jevtron-test-replays")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    """A real uvicorn on a real port — ws + REST + proxy in one fixture."""
    import uvicorn

    from server.app import app

    port = _free_port()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(cfg)
    threading.Thread(target=srv.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(f"{url}/health", timeout=0.2)
            break
        except Exception:
            time.sleep(0.05)
    yield url
    srv.should_exit = True


@pytest.fixture
def gm(server):
    return httpx.Client(base_url=server, headers={"x-gm-password": "test"}, timeout=10)
