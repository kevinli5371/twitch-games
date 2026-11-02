"""Authorization interface. Twitch verification must be implemented separately."""

from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException

from .contracts import Permission


@dataclass(frozen=True)
class Principal:
    user_id: str
    channel_id: str
    is_owner: bool
    permissions: frozenset[Permission]
    identity_shared: bool = False


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal: ...


class UnconfiguredVerifier:
    async def verify(self, token: str) -> Principal:
        raise HTTPException(503, detail={"code": "auth_unconfigured", "message": "Twitch authentication is not configured"})


def require_channel(principal: Principal, channel_id: str) -> None:
    if principal.channel_id != channel_id:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Wrong channel"})


def require_permission(principal: Principal, channel_id: str, permission: Permission) -> None:
    require_channel(principal, channel_id)
    if not principal.is_owner and permission not in principal.permissions:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Permission required"})


def require_permission_admin(principal: Principal, channel_id: str) -> None:
    require_channel(principal, channel_id)
    if not principal.is_owner:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Only the streamer manages moderator access"})
