import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    INTERVIEWING = "INTERVIEWING"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    GHOSTED = "GHOSTED"


class ApplicationCreate(BaseModel):
    company: str
    position: str
    url: str | None = None
    job_description: str
    status: ApplicationStatus = ApplicationStatus.DRAFT
    applied_at: datetime | None = None
    source: str | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    company: str | None = None
    position: str | None = None
    url: str | None = None
    job_description: str | None = None
    status: ApplicationStatus | None = None
    applied_at: datetime | None = None
    source: str | None = None
    notes: str | None = None


class ApplicationResponse(BaseModel):
    id: UUID
    company: str
    position: str
    url: str | None
    job_description: str
    status: ApplicationStatus
    applied_at: datetime | None
    source: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
