"""Uvicorn entrypoint. Invalid environment configuration fails at startup."""

from twitch_games.application import create_app

app = create_app()
