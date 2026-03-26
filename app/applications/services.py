from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.applications.models import JobApplication
from app.applications.schemas import ApplicationCreate, ApplicationUpdate


async def create_application(
    db: AsyncSession, user_id: UUID, data: ApplicationCreate
) -> JobApplication:
    application = JobApplication(user_id=user_id, **data.model_dump())
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


async def get_applications(
    db: AsyncSession, user_id: UUID, status: str | None = None
) -> list[JobApplication]:
    query = select(JobApplication).where(JobApplication.user_id == user_id)
    if status:
        query = query.where(JobApplication.status == status)
    query = query.order_by(JobApplication.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_application(
    db: AsyncSession, user_id: UUID, application_id: UUID
) -> JobApplication | None:
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id, JobApplication.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def update_application(
    db: AsyncSession, application: JobApplication, data: ApplicationUpdate
) -> JobApplication:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    await db.commit()
    await db.refresh(application)
    return application


async def delete_application(db: AsyncSession, application: JobApplication) -> None:
    await db.delete(application)
    await db.commit()
