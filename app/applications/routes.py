from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_application(db, user.id, data)


@router.get("/", response_model=list[ApplicationResponse])
async def list_applications(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_applications(db, user.id, status_filter)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_one(
    application_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await get_application(db, user.id, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


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
