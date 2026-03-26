from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agent.schemas import AIScoreResponse, AIScoreResult, AITaskStatus, ScoreRequest
from app.ai_agent.tasks import run_resume_scoring
from app.applications.models import JobApplication
from app.auth.models import User
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.resumes.models import ResumeVersion

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/score", response_model=AIScoreResponse)
async def trigger_scoring(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        data = ScoreRequest(**body)
    else:
        form = await request.form()
        data = ScoreRequest(
            application_id=UUID(str(form.get("application_id", ""))),
            resume_id=UUID(str(form.get("resume_id", ""))),
        )

    app_result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == data.application_id, JobApplication.user_id == user.id
        )
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    resume_result = await db.execute(
        select(ResumeVersion).where(
            ResumeVersion.id == data.resume_id, ResumeVersion.user_id == user.id
        )
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if not resume.extracted_text:
        raise HTTPException(status_code=400, detail="Resume has no extracted text")

    score_result = AIScoreResult(
        application_id=data.application_id,
        resume_id=data.resume_id,
        model_used=settings.openai_model,
        status=AITaskStatus.PENDING,
    )
    db.add(score_result)
    await db.commit()
    await db.refresh(score_result)

    run_resume_scoring.delay(str(score_result.id))

    if "application/json" not in content_type:
        return RedirectResponse(
            url=f"/ai/results/{score_result.id}", status_code=303
        )

    return score_result


@router.get("/results/{score_id}")
async def view_results(
    score_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIScoreResult)
        .join(JobApplication, AIScoreResult.application_id == JobApplication.id)
        .where(AIScoreResult.id == score_id, JobApplication.user_id == user.id)
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="Score result not found")

    templates = request.app.state.templates
    return templates.TemplateResponse("ai_agent/results.html", {
        "request": request,
        "user": user,
        "csrf_token": request.session.get("csrf_token", ""),
        "score": score,
    })


@router.get("/score/{score_id}", response_model=AIScoreResponse)
async def get_score(
    score_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIScoreResult)
        .join(JobApplication, AIScoreResult.application_id == JobApplication.id)
        .where(AIScoreResult.id == score_id, JobApplication.user_id == user.id)
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="Score result not found")
    return score


@router.get("/scores/{application_id}", response_model=list[AIScoreResponse])
async def list_scores(
    application_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIScoreResult)
        .join(JobApplication, AIScoreResult.application_id == JobApplication.id)
        .where(
            AIScoreResult.application_id == application_id,
            JobApplication.user_id == user.id,
        )
        .order_by(AIScoreResult.created_at.desc())
    )
    return list(result.scalars().all())
