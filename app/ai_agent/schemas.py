import enum
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AITaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIScoreResult(Base):
    __tablename__ = "ai_score_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skill_matches: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw_llm_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[AITaskStatus] = mapped_column(
        Enum(AITaskStatus), default=AITaskStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_score_app_resume_created", "application_id", "resume_id", created_at.desc()),
    )


# Pydantic response schemas
class AIScoreResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    resume_id: uuid.UUID
    overall_score: int | None
    skill_matches: dict | None
    recommendations: list | None
    model_used: str
    status: AITaskStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ScoreRequest(BaseModel):
    application_id: uuid.UUID
    resume_id: uuid.UUID
