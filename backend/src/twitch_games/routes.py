"""Authenticated HTTP boundaries: public state, private participation, owner controls."""

from uuid import UUID

from fastapi import APIRouter, Request

from twitch_games.contracts.models import (
    AnswerSubmission,
    BatchReceipt,
    DashboardSnapshot,
    GameCommand,
    Leaderboard,
    OpenRound,
    OwnParticipation,
    PublicGameState,
    QuestionCandidate,
    StartGame,
    SubmissionReceipt,
    TranscriptBatch,
)
from twitch_games.errors import GameError
from twitch_games.runtime_models import AliasUpdate, GrantUpdate, StreamConnection
from twitch_games.store import one, rows, run

router = APIRouter(prefix="/api/v1")


def context(request):
    auth = request.app.state.auth
    service = request.app.state.game_service
    identity = auth.identity(request)
    target = request.path_params.get("channel_id")
    if identity.source == "dashboard" and target is None:
        for key, table in (
            ("game_id", "game_sessions"),
            ("round_id", "rounds"),
            ("stream_id", "streams"),
        ):
            if key in request.path_params:
                if hasattr(service, "resolve_channel"):
                    target = service.resolve_channel(key, request.path_params[key])
                else:
                    with auth.require_database().transaction() as c:
                        record = one(
                            c,
                            f"SELECT channel_id FROM twitch_games.{table} WHERE id=:id",
                            id=request.path_params[key],
                        )
                    if record is None:
                        raise GameError("not_found", "Resource not found", 404)
                    target = record["channel_id"]
                break
    if target:
        identity = auth.workspace(identity, target)
    return request.app.state.game_service, identity


@router.get("/channels/{channel_id}/game-state", response_model=PublicGameState, tags=["viewer"])
def state(channel_id: str, request: Request):
    service, identity = context(request)
    return service.public_state(identity, channel_id)


@router.get(
    "/dashboard/channels/{channel_id}", response_model=DashboardSnapshot, tags=["dashboard"]
)
def dashboard(channel_id: str, request: Request):
    service, identity = context(request)
    return service.dashboard(identity, channel_id)


@router.post("/channels/{channel_id}/stream", response_model=StreamConnection, tags=["dashboard"])
def stream(channel_id: str, request: Request):
    service, identity = context(request)
    return service.connect_stream(identity, channel_id)


@router.post(
    "/streams/{stream_id}/transcript-batches",
    response_model=BatchReceipt,
    status_code=202,
    tags=["dashboard"],
)
def captions(stream_id: UUID, body: TranscriptBatch, request: Request):
    service, identity = context(request)
    return service.intake(identity, stream_id, body)


@router.get(
    "/streams/{stream_id}/questions", response_model=list[QuestionCandidate], tags=["dashboard"]
)
def questions(stream_id: UUID, request: Request):
    service, identity = context(request)
    if hasattr(service, "questions_http"):
        return service.questions_http(identity, stream_id)
    with service.db().transaction() as c:
        service.resource(c, "streams", stream_id, identity, owner=True)
        return service.questions(c, stream_id)


@router.get("/channels/{channel_id}/aliases", response_model=list[AliasUpdate], tags=["dashboard"])
def aliases(channel_id: str, request: Request):
    service, identity = context(request)
    return service.aliases(identity, channel_id)


@router.put("/channels/{channel_id}/aliases", response_model=list[AliasUpdate], tags=["dashboard"])
def update_aliases(channel_id: str, body: AliasUpdate, request: Request):
    service, identity = context(request)
    return service.aliases(identity, channel_id, body)


@router.post(
    "/channels/{channel_id}/games",
    response_model=PublicGameState,
    status_code=201,
    tags=["dashboard"],
)
def start_game(channel_id: str, body: StartGame, request: Request):
    service, identity = context(request)
    return service.start(identity, channel_id, body)


@router.post(
    "/games/{game_id}/rounds", response_model=PublicGameState, status_code=201, tags=["dashboard"]
)
def open_round(game_id: UUID, body: OpenRound, request: Request):
    service, identity = context(request)
    return service.open_round(identity, game_id, body)


@router.post(
    "/rounds/{round_id}/answers", response_model=SubmissionReceipt, status_code=202, tags=["viewer"]
)
def answer(round_id: UUID, body: AnswerSubmission, request: Request):
    service, identity = context(request)
    return service.submit(identity, round_id, body)


@router.get("/rounds/{round_id}/me", response_model=OwnParticipation, tags=["viewer"])
def own(round_id: UUID, request: Request):
    service, identity = context(request)
    return service.own(identity, round_id)


@router.post(
    "/rounds/{round_id}/close", response_model=PublicGameState, status_code=202, tags=["dashboard"]
)
def close_round(round_id: UUID, body: GameCommand, request: Request):
    service, identity = context(request)
    return service.close_round(identity, round_id, body)


@router.post("/games/{game_id}/end", response_model=PublicGameState, tags=["dashboard"])
def end_game(game_id: UUID, body: GameCommand, request: Request):
    service, identity = context(request)
    return service.end(identity, game_id, body)


@router.get("/games/{game_id}/leaderboard", response_model=Leaderboard, tags=["viewer"])
def leaderboard(game_id: UUID, request: Request):
    service, identity = context(request)
    return service.leaderboard(identity, game_id)


@router.get("/channels/{channel_id}/moderators", tags=["dashboard"])
def list_grants(channel_id: str, request: Request):
    service, identity = context(request)
    if hasattr(service, "grants"):
        return service.grants(identity, channel_id)
    identity.owner(channel_id)
    with service.db().transaction() as c:
        return [
            dict(row)
            for row in rows(
                c,
                "SELECT g.moderator_twitch_id AS user_id,u.login,u.display_name, "
                "array_agg(g.permission ORDER BY g.permission) AS permissions FROM "
                "twitch_games.moderator_grants g "
                "JOIN twitch_games.twitch_users u ON u.id=g.moderator_twitch_id WHERE "
                "channel_id=:channel "
                "GROUP BY g.moderator_twitch_id,u.login,u.display_name ORDER BY u.login",
                channel=channel_id,
            )
        ]


@router.put("/channels/{channel_id}/moderators", tags=["dashboard"])
def set_grants(channel_id: str, body: GrantUpdate, request: Request):
    service, identity = context(request)
    if hasattr(service, "grants"):
        return service.grants(identity, channel_id, body=body)
    identity.owner(channel_id)
    auth = request.app.state.auth
    moderator = auth.provider.user_by_login(body.login)
    if moderator["id"] == channel_id:
        raise GameError("validation_error", "The owner already has all permissions", 422)
    owner = auth.provider.user(channel_id)
    with service.db().transaction() as c:
        service.lock_channel(c, identity)
        auth.save_profile(c, owner)
        auth.save_profile(c, moderator)
        run(
            c,
            "DELETE FROM twitch_games.moderator_grants WHERE channel_id=:channel AND "
            "moderator_twitch_id=:user",
            channel=channel_id,
            user=moderator["id"],
        )
        for permission in body.permissions:
            run(
                c,
                "INSERT INTO twitch_games.moderator_grants "
                "(channel_id,moderator_twitch_id,permission,granted_by) VALUES (:channel,"
                ":user,:permission,:channel)",
                channel=channel_id,
                user=moderator["id"],
                permission=permission,
            )
    return {
        "user_id": moderator["id"],
        "login": moderator["login"],
        "permissions": body.permissions,
    }


@router.delete(
    "/channels/{channel_id}/moderators/{moderator_id}", status_code=204, tags=["dashboard"]
)
def revoke_grants(channel_id: str, moderator_id: str, request: Request):
    from fastapi import Response

    service, identity = context(request)
    if hasattr(service, "grants"):
        service.grants(identity, channel_id, moderator_id=moderator_id)
        return Response(status_code=204)
    identity.owner(channel_id)
    with service.db().transaction() as c:
        service.lock_channel(c, identity)
        run(
            c,
            "DELETE FROM twitch_games.moderator_grants WHERE channel_id=:channel AND "
            "moderator_twitch_id=:user",
            channel=channel_id,
            user=moderator_id,
        )
    return Response(status_code=204)
