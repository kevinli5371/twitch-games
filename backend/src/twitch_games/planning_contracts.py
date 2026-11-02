"""Distinct client boundaries. Private bank models must never feed viewer DTOs."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .domain import Mode


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Permission(StrEnum):
    QUESTION_REVIEW = "question_review"
    LIVE_CONTROL = "live_control"
    SETTINGS = "settings"


class PublicQuestion(Contract):
    id: UUID
    mode: Mode
    prompt: str
    position: int = Field(ge=1)
    total: int = Field(ge=3, le=5)
    deadline: datetime | None = None


class PublicGameState(Contract):
    channel_id: str
    game_id: UUID | None
    round_id: UUID | None
    version: int = Field(ge=0)
    phase: str
    question: PublicQuestion | None
    # No canonical answers, raw submissions, valid-word lists or bank contents.


class SubmitAnswer(Contract):
    # Engineering transport safeguard, not an answer-equivalence/scoring rule.
    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("answer")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Answer cannot be blank")
        return value


class PrivateReceipt(Contract):
    submission_id: UUID
    question_id: UUID
    accepted_at: datetime
    status: str = "accepted"


class PrivilegedQuestion(Contract):
    id: UUID
    channel_id: str
    mode: Mode
    prompt: str
    canonical_answer: str | None
    valid_words: tuple[str, ...] | None
    source_reference: str | None
    review_status: str
    off_cooldown: bool


class DashboardSnapshot(Contract):
    state: PublicGameState
    questions: tuple[PrivilegedQuestion, ...]
    permissions: tuple[Permission, ...]


class ErrorDetail(Contract):
    code: str
    message: str
