from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user
from app.resumes.schemas import ResumeResponse
from app.resumes.services import delete_resume, get_resume, get_resumes, upload_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    request: Request,
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

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url="/resumes", status_code=status.HTTP_303_SEE_OTHER)

    return resume


@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resumes = await get_resumes(db, user.id)

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        templates = request.app.state.templates
        return templates.TemplateResponse("resumes/list.html", {
            "request": request,
            "user": user,
            "csrf_token": request.session.get("csrf_token", ""),
            "resumes": resumes,
        })

    return resumes


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


@router.post("/{resume_id}/delete")
async def delete_from_form(
    resume_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = await get_resume(db, user.id, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    await delete_resume(db, resume)
    return RedirectResponse(url="/resumes", status_code=status.HTTP_303_SEE_OTHER)


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
