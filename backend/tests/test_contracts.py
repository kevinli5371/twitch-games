import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from twitch_games.contracts import models
from twitch_games.contracts.examples import build_examples
from twitch_games.contracts.export import build_contract

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MODELS = {
    "public_idle": models.PublicGameState,
    "public_answering": models.PublicGameState,
    "public_results": models.PublicGameState,
    "submission_request": models.AnswerSubmission,
    "submission_receipt": models.SubmissionReceipt,
    "own_pending": models.OwnParticipation,
    "own_result": models.OwnParticipation,
    "leaderboard": models.Leaderboard,
    "dashboard": models.DashboardSnapshot,
    "transcript_batch": models.TranscriptBatch,
    "batch_receipt": models.BatchReceipt,
    "start_game": models.StartGame,
    "open_round": models.OpenRound,
    "game_command": models.GameCommand,
    "error": models.ErrorEnvelope,
    "state_changed": models.StateChanged,
}


@pytest.mark.parametrize("name", EXAMPLE_MODELS)
def test_frontend_examples_validate_against_contracts(name):
    examples = json.loads((BACKEND_ROOT / "docs/examples.json").read_text())
    EXAMPLE_MODELS[name].model_validate(examples[name])


@pytest.mark.parametrize(
    "key,value",
    [
        ("canonical_answer", "spoon"),
        ("complete_quote", "I cannot believe we won with a spoon."),
        ("accepted_aliases", ["spoon"]),
        ("source", {"text": "secret source"}),
    ],
)
def test_unrevealed_round_rejects_privileged_data(key, value):
    state = build_examples()["public_answering"]
    state["round"][key] = value
    with pytest.raises(ValidationError):
        models.PublicGameState.model_validate(state)


def test_dashboard_cannot_be_serialized_as_public_game():
    dashboard = build_examples()["dashboard"]
    with pytest.raises(ValidationError):
        models.PublicGameState.model_validate(dashboard)
    public = models.PublicGameState.model_validate(dashboard["game"]).model_dump_json()
    assert "spoon" not in public
    assert "canonical_answer" not in public
    assert "source" not in public


def test_answer_receipt_cannot_leak_grade_before_reveal():
    receipt = build_examples()["submission_receipt"]
    receipt["is_correct"] = True
    with pytest.raises(ValidationError):
        models.SubmissionReceipt.model_validate(receipt)


@pytest.mark.parametrize("answer", ["", "   ", "\n", "spoon\x00", "x" * 257])
def test_invalid_answer_requests_are_rejected(answer):
    body = build_examples()["submission_request"]
    body["answer"] = answer
    with pytest.raises(ValidationError):
        models.AnswerSubmission.model_validate(body)


def test_input_is_preserved_and_no_client_verdict_is_accepted():
    body = build_examples()["submission_request"]
    body["answer"] = "  SpOOnn  "
    assert models.AnswerSubmission.model_validate(body).answer == "  SpOOnn  "
    body["is_correct"] = True
    with pytest.raises(ValidationError):
        models.AnswerSubmission.model_validate(body)


def test_timestamps_require_timezone():
    body = build_examples()["public_answering"]
    body["server_time"] = "2026-11-01T18:00:00"
    with pytest.raises(ValidationError):
        models.PublicGameState.model_validate(body)


def test_dashboard_rejects_cross_channel_and_cross_stream_candidates():
    body = build_examples()["dashboard"]
    body["game"]["channel_id"] = "99999"
    with pytest.raises(ValidationError):
        models.DashboardSnapshot.model_validate(body)
    body = build_examples()["dashboard"]
    body["candidates"][0]["source"]["stream_id"] = "wrong-stream"
    with pytest.raises(ValidationError):
        models.DashboardSnapshot.model_validate(body)


def test_event_and_personal_result_require_consistent_identifiers():
    event = build_examples()["state_changed"]
    event["channel_id"] = "99999"
    with pytest.raises(ValidationError):
        models.StateChanged.model_validate(event)
    personal = build_examples()["own_result"]
    personal["result"]["submission_id"] = "someone-else"
    with pytest.raises(ValidationError):
        models.OwnParticipation.model_validate(personal)


def test_game_policy_is_required_not_defaulted():
    body = build_examples()["start_game"]
    del body["policy_id"]
    with pytest.raises(ValidationError):
        models.StartGame.model_validate(body)


def test_contract_exports_are_reproducible_and_have_resolvable_references():
    contract = build_contract()
    assert json.loads((BACKEND_ROOT / "docs/openapi.planned.json").read_text()) == contract
    assert json.loads((BACKEND_ROOT / "docs/examples.json").read_text()) == build_examples()

    def check_references(node):
        if isinstance(node, dict):
            if "$ref" in node:
                target = contract
                for part in node["$ref"].removeprefix("#/").split("/"):
                    target = target[part]
            for value in node.values():
                check_references(value)
        elif isinstance(node, list):
            for value in node:
                check_references(value)

    check_references(contract)
    for operations in contract["paths"].values():
        for operation in operations.values():
            assert operation["x-implementation-status"] == "planned"
            assert operation["security"]
    assert contract["components"]["schemas"]["HiddenRound"]["additionalProperties"] is False


def test_results_are_the_only_phase_that_permits_reveal_fields():
    body = deepcopy(build_examples()["public_results"])
    body["round"]["phase"] = "closed"
    with pytest.raises(ValidationError):
        models.PublicGameState.model_validate(body)
