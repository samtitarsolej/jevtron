# Thin aliases over the turbo tasks, so `make` keeps working.
.PHONY: install test build sim dryrun clone prod spectator dev clean

install:            ## venv + python deps + SDK + node deps
	npm run setup

test:               ## engine + ws + proxy + sdk
	npx turbo test

build:              ## spectator production build (cached)
	npx turbo build

dev:                ## clone server + spectator, in parallel
	npx turbo dev

sim:                ## 4 random bots, ASCII frames, no server
	npm run sim

dryrun:             ## prod server + mock Jev + full tournament + leaderboard
	npm run dryrun

clone:              ## free-play server    (SERVER_PORT, default 8000)
	npm run clone

prod:               ## scored server       (SERVER_PORT, default 8000)
	npm run prod

spectator:          ## next dev            (SPECTATOR_PORT, default 3000)
	npm run spectator

clean:
	rm -rf replays/*.json spectator/.next .turbo node_modules/.cache
