"""Export a planned OpenAPI handoff without mounting unfinished HTTP handlers."""

import argparse
import json
from pathlib import Path
from typing import Any

from twitch_games.contracts import models
from twitch_games.contracts.examples import build_examples

ROOT_MODELS = (
    models.PublicGameState,
    models.AnswerSubmission,
    models.SubmissionReceipt,
    models.OwnParticipation,
    models.Leaderboard,
    models.DashboardSnapshot,
    models.TranscriptBatch,
    models.BatchReceipt,
    models.QuestionCandidate,
    models.StartGame,
    models.OpenRound,
    models.GameCommand,
    models.ErrorEnvelope,
    models.StateChanged,
)


def build_contract() -> dict[str, Any]:
    schemas: dict[str, Any] = {}
    for model in ROOT_MODELS:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        schemas[model.__name__] = schema

    def ref(name: str) -> dict[str, str]:
        return {"$ref": f"#/components/schemas/{name}"}

    def operation(
        operation_id: str,
        audience: str,
        response: str,
        status: str = "200",
        request: str | None = None,
        parameters: tuple[str, ...] = (),
        many: bool = False,
    ) -> dict[str, Any]:
        security = "ViewerExtensionJWT" if audience == "viewer" else "StreamerSession"
        body: dict[str, Any] = {
            "operationId": operation_id,
            "tags": [audience],
            "x-implementation-status": "planned",
            "security": [{security: []}],
            "responses": {
                status: {
                    "description": "Proposed response; endpoint not implemented in Step 1",
                    "content": {
                        "application/json": {
                            "schema": {"type": "array", "items": ref(response)}
                            if many
                            else ref(response)
                        }
                    },
                },
                "default": {
                    "description": "Proposed application error; HTTP mapping in contracts.md",
                    "content": {"application/json": {"schema": ref("ErrorEnvelope")}},
                },
            },
        }
        if parameters:
            body["parameters"] = [
                {
                    "name": parameter,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "minLength": 1},
                }
                for parameter in parameters
            ]
        if request is not None:
            body["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": ref(request)}},
            }
        return body

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Twitch Games — PLANNED gameplay API",
            "version": "0.1.0-draft",
            "description": (
                "Frontend design handoff only. None of these game endpoints are mounted in "
                "Step 1. Runtime OpenAPI lists only health endpoints. Numeric example values "
                "do not establish scoring defaults. Authorization is implemented in Step 3."
            ),
        },
        "x-implementation-status": "planned",
        "x-public-event-schema": ref("StateChanged"),
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "ViewerExtensionJWT": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "Twitch Extension JWT",
                },
                "StreamerSession": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "twitch_games_session",
                    "description": "Proposed OAuth session cookie; auth implemented in Step 3",
                },
            },
        },
        "paths": {
            "/api/v1/channels/{channel_id}/game-state": {
                "get": operation(
                    "getGameState", "viewer", "PublicGameState", parameters=("channel_id",)
                )
            },
            "/api/v1/rounds/{round_id}/answers": {
                "post": operation(
                    "submitAnswer",
                    "viewer",
                    "SubmissionReceipt",
                    "202",
                    "AnswerSubmission",
                    ("round_id",),
                )
            },
            "/api/v1/rounds/{round_id}/me": {
                "get": operation(
                    "getOwnParticipation", "viewer", "OwnParticipation", parameters=("round_id",)
                )
            },
            "/api/v1/games/{game_id}/leaderboard": {
                "get": operation("getLeaderboard", "viewer", "Leaderboard", parameters=("game_id",))
            },
            "/api/v1/dashboard/channels/{channel_id}": {
                "get": operation(
                    "getDashboard", "dashboard", "DashboardSnapshot", parameters=("channel_id",)
                )
            },
            "/api/v1/streams/{stream_id}/transcript-batches": {
                "post": operation(
                    "ingestCaptionBatch",
                    "dashboard",
                    "BatchReceipt",
                    "202",
                    "TranscriptBatch",
                    ("stream_id",),
                )
            },
            "/api/v1/streams/{stream_id}/questions": {
                "get": operation(
                    "getQuestionCandidates",
                    "dashboard",
                    "QuestionCandidate",
                    parameters=("stream_id",),
                    many=True,
                )
            },
            "/api/v1/channels/{channel_id}/games": {
                "post": operation(
                    "startGame",
                    "dashboard",
                    "PublicGameState",
                    "201",
                    "StartGame",
                    ("channel_id",),
                )
            },
            "/api/v1/games/{game_id}/rounds": {
                "post": operation(
                    "openRound", "dashboard", "PublicGameState", "201", "OpenRound", ("game_id",)
                )
            },
            "/api/v1/rounds/{round_id}/close": {
                "post": operation(
                    "closeRound",
                    "dashboard",
                    "PublicGameState",
                    "202",
                    "GameCommand",
                    ("round_id",),
                )
            },
            "/api/v1/games/{game_id}/end": {
                "post": operation(
                    "endGame", "dashboard", "Leaderboard", "200", "GameCommand", ("game_id",)
                )
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/openapi.planned.json"))
    parser.add_argument("--examples-output", type=Path, default=Path("docs/examples.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_contract(), indent=2) + "\n", encoding="utf-8")
    args.examples_output.parent.mkdir(parents=True, exist_ok=True)
    args.examples_output.write_text(json.dumps(build_examples(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
