"""Step 7: same binary, one env switch."""

from server import config, matches


def test_prod_mode_meters_and_scores():
    assert config.MODE == "prod" and config.scored()
    assert matches.create_match(["x", "y"]).budget == config.CONFIG["token_budget"]


def test_clone_mode_is_free_play(monkeypatch):
    monkeypatch.setattr(config, "MODE", "clone")
    assert not config.scored()
    m = matches.create_match(["x", "y"])
    assert m.budget > 10**6  # nobody runs out while practising
    before = dict(matches.LEADERBOARD)
    m.result = matches.score_match(m)
    assert dict(matches.LEADERBOARD) == before  # clone matches never touch the table
