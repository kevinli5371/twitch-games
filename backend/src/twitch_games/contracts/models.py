"""Separate public, private-viewer and privileged-dashboard contracts.

These schemas support frontend development. They do not implement gameplay or
choose a point policy, answer-editing rule, timer length or synonym threshold.
"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

ResourceId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
ChannelId = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$", max_length=32)]
QuoteText = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
AnswerText = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class HiddenRound(Contract):
    round_id: ResourceId
    phase: Literal["prepared", "answering", "closed", "scoring", "cancelled"]
    prompt: QuoteText
    opened_at: AwareDatetime | None
    closes_at: AwareDatetime | None


class RevealedRound(Contract):
    round_id: ResourceId
    phase: Literal["results"]
    prompt: QuoteText
    complete_quote: QuoteText
    canonical_answer: AnswerText


PublicRound = Annotated[HiddenRound | RevealedRound, Field(discriminator="phase")]


class PublicGameState(Contract):
    channel_id: ChannelId
    game_id: ResourceId | None
    status: Literal["idle", "active", "ended"]
    version: int = Field(ge=0)
    server_time: AwareDatetime
    round: PublicRound | None

    @model_validator(mode="after")
    def consistent_game_identity(self) -> Self:
        if self.status == "idle" and (self.game_id is not None or self.round is not None):
            raise ValueError("Idle state cannot contain a game or round")
        if self.status != "idle" and self.game_id is None:
            raise ValueError("An active or ended game needs a game_id")
        if (
            self.status == "ended"
            and self.round is not None
            and self.round.phase not in {"results", "cancelled"}
        ):
            raise ValueError("Ended games cannot advertise a playable round")
        return self


class AnswerSubmission(Contract):
    request_id: UUID
    answer: AnswerText

    @field_validator("answer")
    @classmethod
    def nonblank_answer(cls, answer: str) -> str:
        if not answer.strip() or any(ord(char) < 32 for char in answer):
            raise ValueError("Answer must contain text and no control characters")
        return answer  # Preserve what was typed; normalization is a later server-side step.


class SubmissionReceipt(Contract):
    submission_id: ResourceId
    round_id: ResourceId
    request_id: UUID
    status: Literal["received"]
    received_at: AwareDatetime


class PrivateRoundResult(Contract):
    round_id: ResourceId
    submission_id: ResourceId
    outcome: Literal["correct", "incorrect"]
    awarded_points: int
    scoring_policy_id: ResourceId


class LeaderboardEntry(Contract):
    participant_id: ResourceId
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    rank: int = Field(ge=1)
    points: int


class OwnParticipation(Contract):
    round_id: ResourceId
    receipt: SubmissionReceipt | None
    result: PrivateRoundResult | None

    @model_validator(mode="after")
    def consistent_submission(self) -> Self:
        if self.receipt is not None and self.receipt.round_id != self.round_id:
            raise ValueError("Receipt must belong to the requested round")
        if self.result is not None and (
            self.receipt is None
            or self.result.round_id != self.round_id
            or self.result.submission_id != self.receipt.submission_id
        ):
            raise ValueError("A revealed personal result must match its receipt")
        return self


class Leaderboard(Contract):
    game_id: ResourceId
    version: int = Field(ge=0)
    final: bool
    entries: list[LeaderboardEntry]
    own_entry: LeaderboardEntry | None


class SourceReference(Contract):
    stream_id: ResourceId
    segment_ids: list[ResourceId] = Field(min_length=1)
    received_at: AwareDatetime


class QuestionCandidate(Contract):
    question_id: ResourceId
    complete_quote: QuoteText
    prompt: QuoteText
    canonical_answer: AnswerText
    accepted_aliases: list[AnswerText]
    source: SourceReference


class TranscriptStatus(Contract):
    status: Literal["not_connected", "waiting", "receiving", "stale"]
    last_received_at: AwareDatetime | None


class DashboardSnapshot(Contract):
    channel_id: ChannelId
    stream_id: ResourceId | None
    transcript: TranscriptStatus
    candidates: list[QuestionCandidate]
    game: PublicGameState
    submission_count: int = Field(ge=0)

    @model_validator(mode="after")
    def one_channel(self) -> Self:
        if self.game.channel_id != self.channel_id:
            raise ValueError("Dashboard and game channel must match")
        if self.candidates and self.stream_id is None:
            raise ValueError("Question candidates require a stream")
        if any(candidate.source.stream_id != self.stream_id for candidate in self.candidates):
            raise ValueError("Candidate source must belong to the dashboard stream")
        return self


class CaptionSegment(Contract):
    sequence: int = Field(ge=0)
    text: QuoteText
    observed_at: AwareDatetime


class TranscriptBatch(Contract):
    batch_id: UUID
    source: Literal["twitch_player_captions"]
    segments: list[CaptionSegment] = Field(min_length=1, max_length=100)


class BatchReceipt(Contract):
    batch_id: UUID
    status: Literal["received", "duplicate"]


class StartGame(Contract):
    request_id: UUID
    mode: Literal["quote"]
    policy_id: ResourceId


class OpenRound(Contract):
    request_id: UUID
    question_id: ResourceId
    expected_version: int = Field(ge=0)


class GameCommand(Contract):
    request_id: UUID
    expected_version: int = Field(ge=0)


class ErrorDetail(Contract):
    code: Literal[
        "unauthenticated",
        "forbidden",
        "validation_error",
        "not_found",
        "stale_state",
        "round_closed",
        "request_conflict",
        "transcript_unavailable",
        "policy_unresolved",
    ]
    message: str


class ErrorEnvelope(Contract):
    error: ErrorDetail


class StateChanged(Contract):
    event: Literal["game_state_changed"]
    channel_id: ChannelId
    version: int = Field(ge=0)
    state: PublicGameState

    @model_validator(mode="after")
    def consistent_state(self) -> Self:
        if self.channel_id != self.state.channel_id or self.version != self.state.version:
            raise ValueError("Event identifiers must match the enclosed public state")
        return self
