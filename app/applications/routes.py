from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agent.schemas import AIScoreResult
from app.applications.models import ApplicationStatus, JobApplication
from app.applications.schemas import ApplicationCreate, ApplicationResponse, ApplicationUpdate
from app.applications.services import (
    create_application,
    delete_application,
    get_application,
    get_applications,
    update_application,
)
from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user
from app.resumes.services import get_resumes

router = APIRouter(prefix="/applications", tags=["applications"])


# --- HTML view routes ---


@router.get("/new")
async def create_form(
    request: Request,
    user: User = Depends(get_current_user),
):
    templates = request.app.state.templates
    return templates.TemplateResponse("applications/create.html", {
        "request": request,
        "user": user,
        "csrf_token": request.session.get("csrf_token", ""),
        "statuses": list(ApplicationStatus),
    })


@router.post("/new")
async def create_from_form(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = ApplicationCreate(
        company=str(form.get("company", "")),
        position=str(form.get("position", "")),
        url=str(form.get("url", "")) or None,
        job_description=str(form.get("job_description", "")),
        status=ApplicationStatus(str(form.get("status", "DRAFT"))),
        source=str(form.get("source", "")) or None,
        notes=str(form.get("notes", "")) or None,
    )
    app = await create_application(db, user.id, data)
    return RedirectResponse(url=f"/applications/{app.id}", status_code=status.HTTP_303_SEE_OTHER)


# --- API routes ---


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_application(db, user.id, data)


@router.get("/", response_model=list[ApplicationResponse])
async def list_applications(
    request: Request,
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    accept = request.headers.get("accept", "")
    applications = await get_applications(db, user.id, status_filter)

    if "text/html" in accept:
        templates = request.app.state.templates
        return templates.TemplateResponse("applications/list.html", {
            "request": request,
            "user": user,
            "csrf_token": request.session.get("csrf_token", ""),
            "applications": applications,
            "statuses": list(ApplicationStatus),
            "status_filter": status_filter,
        })

    return applications


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_one(
    application_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await get_application(db, user.id, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        templates = request.app.state.templates
        resumes = await get_resumes(db, user.id)

        scores_result = await db.execute(
            select(AIScoreResult)
            .where(AIScoreResult.application_id == application_id)
            .order_by(AIScoreResult.created_at.desc())
        )
        scores = list(scores_result.scalars().all())

        return templates.TemplateResponse("applications/detail.html", {
            "request": request,
            "user": user,
            "csrf_token": request.session.get("csrf_token", ""),
            "application": app,
            "statuses": list(ApplicationStatus),
            "resumes": resumes,
            "scores": scores,
        })

    return app


@router.post("/{application_id}")
async def update_from_form(
    application_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await get_application(db, user.id, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    form = await request.form()
    data = ApplicationUpdate(
        company=str(form.get("company", "")) or None,
        position=str(form.get("position", "")) or None,
        url=str(form.get("url", "")) or None,
        job_description=str(form.get("job_description", "")) or None,
        status=ApplicationStatus(str(form.get("status", ""))) if form.get("status") else None,
        source=str(form.get("source", "")) or None,
        notes=str(form.get("notes", "")) or None,
    )
    await update_application(db, app, data)
    return RedirectResponse(url=f"/applications/{application_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update(
    application_id: UUID,
    data: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await get_application(db, user.id, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return await update_application(db, app, data)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    application_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await get_application(db, user.id, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await delete_application(db, app)
