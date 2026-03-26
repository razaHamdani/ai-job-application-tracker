import io
import os
import uuid as uuid_mod
from uuid import UUID

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.resumes.models import ResumeVersion


def extract_text_from_pdf(file: io.BytesIO) -> str:
    reader = PdfReader(file)
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n".join(text_parts)


async def upload_resume(
    db: AsyncSession,
    user_id: UUID,
    filename: str,
    file_content: bytes,
    version_label: str | None = None,
) -> ResumeVersion:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_content) > max_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_size_mb}MB limit")

    ext = ".pdf"
    safe_filename = f"{uuid_mod.uuid4()}{ext}"
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    extracted_text = extract_text_from_pdf(io.BytesIO(file_content))

    resume = ResumeVersion(
        user_id=user_id,
        filename=filename,
        file_path=file_path,
        extracted_text=extracted_text,
        version_label=version_label,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


async def get_resumes(db: AsyncSession, user_id: UUID) -> list[ResumeVersion]:
    result = await db.execute(
        select(ResumeVersion)
        .where(ResumeVersion.user_id == user_id)
        .order_by(ResumeVersion.created_at.desc())
    )
    return list(result.scalars().all())


async def get_resume(db: AsyncSession, user_id: UUID, resume_id: UUID) -> ResumeVersion | None:
    result = await db.execute(
        select(ResumeVersion).where(
            ResumeVersion.id == resume_id, ResumeVersion.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def delete_resume(db: AsyncSession, resume: ResumeVersion) -> None:
    if os.path.exists(resume.file_path):
        os.remove(resume.file_path)
    await db.delete(resume)
    await db.commit()
