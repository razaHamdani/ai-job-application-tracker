from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: UUID
    filename: str
    version_label: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
