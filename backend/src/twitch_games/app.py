"""Runnable health/contract API. Gameplay endpoints fail closed until integrated."""

import os
from dataclasses import dataclass

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import Principal, TokenVerifier, UnconfiguredVerifier, require_channel
from .contracts import DashboardSnapshot, PublicGameState


@dataclass(frozen=True)
class Settings:
    database_url: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(database_url=os.environ.get("DATABASE_URL") or None)


def create_app(verifier: TokenVerifier | None = None) -> FastAPI:
    api = FastAPI(title="Twitch Games foundation", version="0.1.0")
    auth = verifier if verifier is not None else UnconfiguredVerifier()
    bearer = HTTPBearer(auto_error=False)

    async def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
        if credentials is None:
            raise HTTPException(401, detail={"code": "unauthenticated", "message": "Authentication required"})
        return await auth.verify(credentials.credentials)

    @api.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive", "implementation": "foundation"}

    @api.get("/health/ready", responses={503: {"description": "Integrations not ready"}})
    async def ready() -> None:
        # A configured URL is not proof of database connectivity or durability.
        raise HTTPException(503, detail={"code": "not_ready", "message": "Database repository and Twitch authentication are not integrated"})

    @api.get("/channels/{channel_id}/game-state", response_model=PublicGameState)
    async def public_state(channel_id: str, identity: Principal = Depends(principal)) -> PublicGameState:
        require_channel(identity, channel_id)
        raise HTTPException(503, detail={"code": "repository_unconfigured", "message": "Durable game repository is not integrated"})

    @api.get("/dashboard/channels/{channel_id}", response_model=DashboardSnapshot)
    async def dashboard(channel_id: str, identity: Principal = Depends(principal)) -> DashboardSnapshot:
        require_channel(identity, channel_id)
        # This DTO includes hidden answers. Moderator hidden-answer access is
        # unresolved; a settings/live-control grant must never imply that access.
        if not identity.is_owner:
            raise HTTPException(403, detail={"code": "forbidden", "message": "Owner access required for privileged snapshot"})
        raise HTTPException(503, detail={"code": "repository_unconfigured", "message": "Durable dashboard repository is not integrated"})

    return api


app = create_app()
