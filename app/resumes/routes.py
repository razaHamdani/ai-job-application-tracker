from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user
from app.resumes.schemas import ResumeResponse
from app.resumes.services import delete_resume, get_resume, get_resumes, upload_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile,
    version_label: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    try:
        resume = await upload_resume(db, user.id, file.filename, content, version_label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return resume


@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_resumes(db, user.id)


@router.get("/{resume_id}/download")
async def download(
    resume_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = await get_resume(db, user.id, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return FileResponse(resume.file_path, filename=resume.filename, media_type="application/pdf")


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    resume_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = await get_resume(db, user.id, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    await delete_resume(db, resume)
