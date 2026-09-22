from server import engine, sim
from server.engine import Config


def game(**kw):
    cfg = Config(w=10, h=10, max_ticks=50, **kw)
    return engine.new_game(cfg, ["a", "b", "c", "d"])


def test_edge_kills():
    s = game()
    s.players = [engine.Player(id="a", pos=(0, 5), dir="W", trail=[(0, 5)])]
    s = engine.step(s, {"a": "W"})
    assert not s.player("a").alive and s.player("a").died_tick == 1


def test_own_trail_kills():
    s = game()
    s.players = [engine.Player(id="a", pos=(5, 5), dir="N", trail=[(5, 6), (5, 5)])]
    s = engine.step(s, {"a": "E"})  # fine
    s = engine.step(s, {"a": "S"})
    s = engine.step(s, {"a": "W"})  # back into own trail at (5,6)
    assert not s.player("a").alive


def test_head_on_kills_both():
    s = game()
    s.players = [
        engine.Player(id="a", pos=(4, 5), dir="E", trail=[(4, 5)]),
        engine.Player(id="b", pos=(6, 5), dir="W", trail=[(6, 5)]),
    ]
    s = engine.step(s, {"a": "E", "b": "W"})  # both want (5,5)
    assert not s.player("a").alive and not s.player("b").alive


def test_no_180():
    s = game()
    s.players = [engine.Player(id="a", pos=(5, 5), dir="E", trail=[(4, 5), (5, 5)])]
    s = engine.step(s, {"a": "W"})  # reversal ignored -> keeps going E
    assert s.player("a").alive and s.player("a").pos == (6, 5)


def test_missing_move_is_autopilot():
    s = game()
    before = s.player("a")
    s2 = engine.step(s, {})
    assert s2.player("a").dir == before.dir and s2.player("a").alive


def test_timeout_finishes():
    cfg = Config(w=40, h=40, max_ticks=3, seed=1)
    s = engine.new_game(cfg, ["a", "b", "c", "d"])
    while not engine.is_finished(s):
        s = engine.step(s, {})
    assert s.tick == 3 and len(s.alive()) > 1


def test_shrink_closes_the_arena():
    cfg = Config(w=10, h=10, max_ticks=50, shrink_every=1, seed=1)
    s = engine.new_game(cfg, ["a", "b", "c", "d"])
    for _ in range(5):
        s = engine.step(s, {})
    assert s.shrink == 5 and not s.alive()


def test_bonus_tile_collected():
    cfg = Config(w=10, h=10, max_ticks=50, seed=3, bonus_tiles=1)
    s = engine.new_game(cfg, ["a"])
    s.bonuses = {(5, 3)}
    s.players = [engine.Player(id="a", pos=(5, 5), dir="N", trail=[(5, 5)])]
    s = engine.step(s, {"a": "N"})
    s = engine.step(s, {"a": "N"})
    assert s.player("a").bonus == 1 and not s.bonuses


def test_fog_hides_the_far_side():
    cfg = Config(w=10, h=10, fog_radius=2, seed=1)
    s = engine.new_game(cfg, ["a", "b"])
    rows = engine.render(s, fog_for="a")
    assert rows[0].count("?") > 0
    assert "?" not in "".join(engine.render(s))  # spectator sees everything


def test_determinism():
    a = sim.run(Config(w=20, h=20, max_ticks=100, seed=42))
    b = sim.run(Config(w=20, h=20, max_ticks=100, seed=42))
    c = sim.run(Config(w=20, h=20, max_ticks=100, seed=43))
    assert a == b and a != c
