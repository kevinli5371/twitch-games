"""Owner-confirmed quote-game rules, snapshotted into each game and round."""

from twitch_games.matching import MATCHER_VERSION

POLICY_ID = "quote_v1"
POLICY = {
    "round_seconds": 30,
    "correct_points": 1,
    "incorrect_points": 0,
    "speed_bonus": False,
    "editable_until_close": True,
    "shared_tie_ranks": True,
    "score_scope": "game",
    "matcher_version": MATCHER_VERSION,
}
