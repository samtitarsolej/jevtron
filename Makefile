PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: install test sim dryrun clone prod spectator clean

install:            ## venv + server deps + editable SDK
	python3 -m venv .venv
	$(PIP) install -q -r requirements.txt
	$(PIP) install -q -e ./sdk

test:               ## engine + ws + proxy + sdk
	$(PY) -m pytest tests -q

sim:                ## 4 random bots, ASCII frames, no server
	$(PY) -m server.sim

dryrun:             ## prod server + mock Jev + full tournament + leaderboard
	$(PY) tools/dryrun.py

clone:              ## free-play server on :8000
	MODE=clone $(PY) -m uvicorn server.app:app --host 0.0.0.0 --port 8000

prod:               ## scored server on :8000
	MODE=prod $(PY) -m uvicorn server.app:app --host 0.0.0.0 --port 8000

spectator:          ## next dev on :3000
	cd spectator && npm install && npm run dev

clean:
	rm -rf replays/*.json spectator/.next
