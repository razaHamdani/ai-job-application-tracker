from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.applications.models import ApplicationStatus, JobApplication
from app.auth.models import User
from app.auth.schemas import LoginRequest
from app.auth.services import create_access_token, verify_password
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("login.html", {
        "request": request,
        "csrf_token": request.session.get("csrf_token", ""),
    })


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        data = LoginRequest(**(await request.json()))
        username = data.username
        password = data.password
    else:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        if "application/json" in content_type:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        templates = request.app.state.templates
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": request.session.get("csrf_token", ""),
            "error": "Invalid username or password",
        })

    token = create_access_token(str(user.id))

    if "application/json" in content_type:
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="strict",
            max_age=settings.jwt_expire_minutes * 60,
        )
        return {"message": "Login successful"}

    redirect = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return redirect


@router.post("/logout")
async def logout(request: Request, response: Response):
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        response.delete_cookie("access_token")
        return {"message": "Logged out"}

    redirect = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie("access_token")
    return redirect


@router.get("/dashboard", include_in_schema=False)
async def dashboard_redirect(request: Request):
    return RedirectResponse(url="/dashboard")


# Dashboard is mounted at /dashboard, not under /auth prefix
dashboard_router = APIRouter(tags=["views"])


@dashboard_router.get("/dashboard")
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    templates = request.app.state.templates

    # Stats
    total_result = await db.execute(
        select(func.count()).select_from(JobApplication).where(JobApplication.user_id == user.id)
    )
    total = total_result.scalar() or 0

    active_statuses = [
        ApplicationStatus.APPLIED,
        ApplicationStatus.SCREENING,
        ApplicationStatus.INTERVIEWING,
    ]
    active_result = await db.execute(
        select(func.count())
        .select_from(JobApplication)
        .where(JobApplication.user_id == user.id, JobApplication.status.in_(active_statuses))
    )
    active = active_result.scalar() or 0

    offers_result = await db.execute(
        select(func.count())
        .select_from(JobApplication)
        .where(JobApplication.user_id == user.id, JobApplication.status == ApplicationStatus.OFFER)
    )
    offers = offers_result.scalar() or 0

    # Recent applications
    recent_result = await db.execute(
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(JobApplication.updated_at.desc())
        .limit(5)
    )
    recent = list(recent_result.scalars().all())

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "csrf_token": request.session.get("csrf_token", ""),
        "stats": {"total": total, "active": active, "offers": offers},
        "recent": recent,
    })
