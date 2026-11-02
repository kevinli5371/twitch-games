"""Artificial, deterministic frontend fixtures. No live capture or game engine."""

from copy import deepcopy
from typing import Any

NOW = "2026-11-01T18:00:00Z"
REQUEST_ID = "11111111-1111-4111-8111-111111111111"


def build_examples() -> dict[str, Any]:
    answering = {
        "channel_id": "12345",
        "game_id": "example-game",
        "status": "active",
        "version": 1,
        "server_time": NOW,
        "round": {
            "round_id": "example-round",
            "phase": "answering",
            "prompt": "I cannot believe we won with a ____.",
            "opened_at": NOW,
            "closes_at": None,
        },
    }
    results = deepcopy(answering)
    results["version"] = 2
    results["round"] = {
        "round_id": "example-round",
        "phase": "results",
        "prompt": "I cannot believe we won with a ____.",
        "complete_quote": "I cannot believe we won with a spoon.",
        "canonical_answer": "spoon",
    }
    receipt = {
        "submission_id": "example-submission",
        "round_id": "example-round",
        "request_id": REQUEST_ID,
        "status": "received",
        "received_at": NOW,
    }
    result = {
        "round_id": "example-round",
        "submission_id": "example-submission",
        "outcome": "correct",
        "awarded_points": 1,
        "scoring_policy_id": "example-policy-not-a-default",
    }
    entry = {
        "participant_id": "example-player",
        "display_name": "ExampleViewer",
        "rank": 1,
        "points": 1,
    }
    return {
        "public_idle": {
            "channel_id": "12345",
            "game_id": None,
            "status": "idle",
            "version": 0,
            "server_time": NOW,
            "round": None,
        },
        "public_answering": answering,
        "public_results": results,
        "submission_request": {"request_id": REQUEST_ID, "answer": "spoonn"},
        "submission_receipt": receipt,
        "own_pending": {"round_id": "example-round", "receipt": receipt, "result": None},
        "own_result": {"round_id": "example-round", "receipt": receipt, "result": result},
        "leaderboard": {
            "game_id": "example-game",
            "version": 2,
            "final": False,
            "entries": [entry],
            "own_entry": entry,
        },
        "dashboard": {
            "channel_id": "12345",
            "stream_id": "example-stream",
            "transcript": {"status": "receiving", "last_received_at": NOW},
            "candidates": [
                {
                    "question_id": "00000000-0000-4000-8000-000000000005",
                    "complete_quote": "I cannot believe we won with a spoon.",
                    "prompt": "I cannot believe we won with a ____.",
                    "canonical_answer": "spoon",
                    "accepted_aliases": [],
                    "source": {
                        "stream_id": "example-stream",
                        "segment_ids": ["example-segment"],
                        "received_at": NOW,
                    },
                }
            ],
            "game": deepcopy(answering),
            "submission_count": 1,
        },
        "transcript_batch": {
            "batch_id": REQUEST_ID,
            "source": "twitch_player_captions",
            "segments": [
                {
                    "sequence": 0,
                    "text": "I cannot believe we won with a spoon.",
                    "observed_at": NOW,
                }
            ],
        },
        "batch_receipt": {"batch_id": REQUEST_ID, "status": "received"},
        "start_game": {
            "request_id": REQUEST_ID,
            "mode": "quote",
            "policy_id": "example-policy-not-a-default",
        },
        "open_round": {
            "request_id": REQUEST_ID,
            "question_id": "00000000-0000-4000-8000-000000000005",
            "expected_version": 0,
        },
        "game_command": {"request_id": REQUEST_ID, "expected_version": 1},
        "error": {"error": {"code": "round_closed", "message": "This round is closed."}},
        "state_changed": {
            "event": "game_state_changed",
            "channel_id": "12345",
            "version": 1,
            "state": deepcopy(answering),
        },
    }
