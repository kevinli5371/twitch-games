"""Additional implemented API inputs and privileged output contracts."""

from typing import Literal

from pydantic import Field, field_validator

from twitch_games.contracts.models import AnswerText, Contract, ResourceId
from twitch_games.matching import normalize_answer


class StreamConnection(Contract):
    stream_id: ResourceId
    twitch_stream_id: ResourceId


class AliasUpdate(Contract):
    canonical: AnswerText
    aliases: list[AnswerText] = Field(max_length=50)

    @field_validator("canonical")
    @classmethod
    def valid_canonical(cls, value):
        normalized = normalize_answer(value)
        if not normalized:
            raise ValueError("Canonical answer must contain text")
        return normalized

    @field_validator("aliases")
    @classmethod
    def valid_aliases(cls, values):
        normalized = [normalize_answer(value) for value in values]
        if any(not value for value in normalized):
            raise ValueError("Aliases must contain text")
        return list(dict.fromkeys(normalized))


class GrantUpdate(Contract):
    login: str = Field(pattern=r"^[A-Za-z0-9_]{1,25}$")
    permissions: list[Literal["question_review", "live_control", "settings"]] = Field(max_length=3)

    @field_validator("permissions")
    @classmethod
    def unique_permissions(cls, values):
        return sorted(set(values))


Permission = Literal["question_review", "live_control", "settings"]


class TwitchProfile(Contract):
    user_id: str
    login: str | None
    display_name: str | None
    avatar_url: str | None


class OwnedChannel(Contract):
    channel_id: str
    display_name: str | None


class WorkspaceAccess(Contract):
    channel_id: str
    role: Literal["owner", "moderator"]
    permissions: list[Permission]


class WorkspaceInfo(WorkspaceAccess):
    display_name: str | None


class DashboardIdentity(Contract):
    user: TwitchProfile
    owned_channel: OwnedChannel
    workspaces: list[WorkspaceInfo]
    selected_workspace: WorkspaceAccess
    csrf_token: str | None
