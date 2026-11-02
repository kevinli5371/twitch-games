"""Compatibility entry point for the application introduced by PR #1.

Both twitch_games.app:app and twitch_games.main:app use the same implemented
application factory; there is no second verifier or repository authority.
"""

from twitch_games.application import create_app

app = create_app()
