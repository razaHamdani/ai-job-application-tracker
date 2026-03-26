# AI Job Application Tracker -- Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a personal, login-protected job application tracker with AI-powered resume scoring using FastAPI, PostgreSQL, Redis, and OpenAI.

**Architecture:** Modular monolith with domain packages (auth, applications, resumes, ai_agent). Server-rendered Jinja2 UI. Celery background tasks for AI operations. Single user, JWT auth.

**Tech Stack:** Python, FastAPI, SQLAlchemy (async), PostgreSQL, Redis, Celery, OpenAI, Alembic, Jinja2, Pico CSS, pypdf

**Design Doc:** `docs/plans/2026-03-24-system-design.md`

---

## Task 1: Project Skeleton & Config

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/main.py`
- Modify: `.gitignore` (add `uploads/`)

**Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.30.0
alembic==1.13.0
pydantic-settings==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
celery[redis]==5.4.0
redis==5.1.0
openai==1.50.0
pypdf==5.0.0
jinja2==3.1.4
python-multipart==0.0.12
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
```

**Step 2: Create .env.example**

```
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/job_tracker

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth -- generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=CHANGE-ME-generate-with-command-above
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
OPENAI_DAILY_CALL_LIMIT=100

# App
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=5
```

**Step 3: Create docker-compose.yml**

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: job_tracker
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

**Step 4: Create app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_daily_call_limit: int = 100

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 5

    model_config = {"env_file": ".env"}

    def validate_secrets(self) -> None:
        if self.jwt_secret in ("CHANGE-ME-generate-with-command-above", "change-me"):
            raise ValueError(
                "JWT_SECRET is still a placeholder. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if self.openai_api_key == "sk-your-key-here":
            raise ValueError("OPENAI_API_KEY is still a placeholder.")


settings = Settings()
```

**Step 5: Create app/__init__.py**

```python
```

(Empty file.)

**Step 6: Create app/main.py**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="AI Job Application Tracker")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

**Step 7: Add uploads/ to .gitignore**

Append to existing `.gitignore`:
```
# Uploads
uploads/
```

**Step 8: Verify the skeleton boots**

Run: `docker-compose up -d`
Run: `pip install -r requirements.txt`
Run: `uvicorn app.main:app --reload`
Run: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

**Step 9: Commit**

```bash
git add requirements.txt .env.example docker-compose.yml app/__init__.py app/config.py app/main.py .gitignore
git commit -m "WIP: add project skeleton, config, docker-compose, health endpoint"
```

---

## Task 2: Database Setup & Alembic

**Files:**
- Create: `app/database.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/` (directory)

**Step 1: Create app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

**Step 2: Initialize Alembic**

Run: `alembic init migrations`
This creates `alembic.ini` at project root and `migrations/` directory.

**Step 3: Configure alembic.ini**

Set `sqlalchemy.url` to empty (we'll override in env.py):
```ini
sqlalchemy.url =
```

**Step 4: Configure migrations/env.py**

Replace the `run_migrations_online` function to use our async engine and import Base metadata. Key changes:
- Import `Base` from `app.database`
- Set `target_metadata = Base.metadata`
- Use `run_async` with our engine for online migrations
- Import all model modules so autogenerate detects them

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base

# Import all models so Alembic detects them
from app.auth.models import *  # noqa: F401, F403
from app.applications.models import *  # noqa: F401, F403
from app.resumes.models import *  # noqa: F401, F403
from app.ai_agent import schemas as ai_schemas  # noqa: F401 (AIScoreResult model)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url.replace("+asyncpg", "")
    connectable = async_engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Note:** The model imports will fail until Task 3 creates them. This file will be finalized after models exist.

**Step 5: Commit**

```bash
git add app/database.py alembic.ini migrations/
git commit -m "WIP: add database setup and Alembic migration config"
```

---

## Task 3: Auth Domain -- User Model, JWT, CLI

**Files:**
- Create: `app/auth/__init__.py`
- Create: `app/auth/models.py`
- Create: `app/auth/schemas.py`
- Create: `app/auth/services.py`
- Create: `app/auth/routes.py`
- Create: `app/cli.py`
- Create: `app/dependencies.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/auth/__init__.py`
- Create: `tests/auth/test_auth_service.py`
- Create: `tests/auth/test_auth_routes.py`

**Step 1: Write failing test for password hashing**

```python
# tests/auth/test_auth_service.py
from app.auth.services import hash_password, verify_password


def test_hash_and_verify_password():
    password = "testpass123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpass", hashed) is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/auth/test_auth_service.py::test_hash_and_verify_password -v`
Expected: FAIL (ImportError)

**Step 3: Implement User model and auth service**

```python
# app/auth/__init__.py
```

```python
# app/auth/models.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

```python
# app/auth/schemas.py
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
```

```python
# app/auth/services.py
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/auth/test_auth_service.py::test_hash_and_verify_password -v`
Expected: PASS

**Step 5: Write failing test for JWT token creation and decoding**

```python
# tests/auth/test_auth_service.py (append)
from app.auth.services import create_access_token, decode_access_token


def test_create_and_decode_token():
    user_id = "test-user-id"
    token = create_access_token(user_id)
    payload = decode_access_token(token)
    assert payload["sub"] == user_id
```

**Step 6: Run test to verify it passes** (already implemented above)

Run: `pytest tests/auth/test_auth_service.py::test_create_and_decode_token -v`
Expected: PASS

**Step 7: Create dependencies.py**

```python
# app/dependencies.py
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.services import decode_access_token
from app.database import get_db


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

**Step 8: Create auth routes**

```python
# app/auth/routes.py
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import LoginRequest
from app.auth.services import create_access_token, verify_password
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 24,
    )
    return {"message": "Login successful"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}
```

**Step 9: Create CLI for user creation**

```python
# app/cli.py
import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.services import hash_password
from app.database import async_session


async def create_user(username: str, password: str) -> None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            return
        user = User(username=username, password_hash=hash_password(password))
        session.add(user)
        await session.commit()
        print(f"User '{username}' created successfully.")


def main():
    parser = argparse.ArgumentParser(description="AI Job Tracker CLI")
    subparsers = parser.add_subparsers(dest="command")

    create_cmd = subparsers.add_parser("create-user")
    create_cmd.add_argument("--username", required=True)
    create_cmd.add_argument("--password", required=True)

    args = parser.parse_args()

    if args.command == "create-user":
        asyncio.run(create_user(args.username, args.password))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 10: Register auth routes in main.py**

Update `app/main.py`:
```python
from fastapi import FastAPI

from app.auth.routes import router as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Job Application Tracker")
    app.include_router(auth_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

**Step 11: Commit**

```bash
git add app/auth/ app/cli.py app/dependencies.py app/main.py tests/
git commit -m "WIP: add auth domain -- User model, JWT, password hashing, login/logout, CLI"
```

---

## Task 4: Applications Domain -- Model & CRUD

**Files:**
- Create: `app/applications/__init__.py`
- Create: `app/applications/models.py`
- Create: `app/applications/schemas.py`
- Create: `app/applications/services.py`
- Create: `app/applications/routes.py`
- Create: `tests/applications/__init__.py`
- Create: `tests/applications/test_application_service.py`

**Step 1: Write failing test for application creation**

```python
# tests/applications/test_application_service.py
import pytest
from app.applications.schemas import ApplicationCreate, ApplicationStatus


def test_application_create_schema():
    data = ApplicationCreate(
        company="Acme Corp",
        position="Backend Engineer",
        job_description="We need a Python dev...",
        status=ApplicationStatus.DRAFT,
        source="LinkedIn",
    )
    assert data.company == "Acme Corp"
    assert data.status == ApplicationStatus.DRAFT
    assert data.url is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/applications/test_application_service.py::test_application_create_schema -v`
Expected: FAIL (ImportError)

**Step 3: Implement Application model and schemas**

```python
# app/applications/__init__.py
```

```python
# app/applications/models.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    INTERVIEWING = "INTERVIEWING"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    GHOSTED = "GHOSTED"


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.DRAFT
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

```python
# app/applications/schemas.py
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/applications/test_application_service.py::test_application_create_schema -v`
Expected: PASS

**Step 5: Implement services and routes**

```python
# app/applications/services.py
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
```

```python
# app/applications/routes.py
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
```

**Step 6: Register routes in main.py**

Add to `app/main.py`:
```python
from app.applications.routes import router as applications_router
# inside create_app():
app.include_router(applications_router)
```

**Step 7: Commit**

```bash
git add app/applications/ tests/applications/
git commit -m "WIP: add applications domain -- model, CRUD service, API routes"
```

---

## Task 5: Resumes Domain -- Model, Upload, PDF Extraction

**Files:**
- Create: `app/resumes/__init__.py`
- Create: `app/resumes/models.py`
- Create: `app/resumes/schemas.py`
- Create: `app/resumes/services.py`
- Create: `app/resumes/routes.py`
- Create: `tests/resumes/__init__.py`
- Create: `tests/resumes/test_resume_service.py`

**Step 1: Write failing test for PDF text extraction**

```python
# tests/resumes/test_resume_service.py
import io

from pypdf import PdfWriter

from app.resumes.services import extract_text_from_pdf


def test_extract_text_from_pdf():
    # Create a minimal PDF in memory
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    # pypdf blank pages have no text, so we test the function runs without error
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)

    text = extract_text_from_pdf(buffer)
    assert isinstance(text, str)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/resumes/test_resume_service.py::test_extract_text_from_pdf -v`
Expected: FAIL (ImportError)

**Step 3: Implement Resume model, service, and schemas**

```python
# app/resumes/__init__.py
```

```python
# app/resumes/models.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

```python
# app/resumes/schemas.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: UUID
    filename: str
    version_label: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

```python
# app/resumes/services.py
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
    # Validate file size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_content) > max_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_size_mb}MB limit")

    # Generate UUID filename to prevent path traversal
    ext = ".pdf"
    safe_filename = f"{uuid_mod.uuid4()}{ext}"
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, safe_filename)

    # Save file
    with open(file_path, "wb") as f:
        f.write(file_content)

    # Extract text
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
    # Clean up file from disk
    if os.path.exists(resume.file_path):
        os.remove(resume.file_path)
    await db.delete(resume)
    await db.commit()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/resumes/test_resume_service.py::test_extract_text_from_pdf -v`
Expected: PASS

**Step 5: Implement routes**

```python
# app/resumes/routes.py
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
```

**Step 6: Register routes in main.py**

Add to `app/main.py`:
```python
from app.resumes.routes import router as resumes_router
# inside create_app():
app.include_router(resumes_router)
```

**Step 7: Commit**

```bash
git add app/resumes/ tests/resumes/
git commit -m "WIP: add resumes domain -- model, PDF upload/extraction, CRUD routes"
```

---

## Task 6: Redis Setup & Celery Worker

**Files:**
- Create: `app/redis.py`
- Create: `celery_worker.py`

**Step 1: Create app/redis.py**

```python
import hashlib
import json
import re

from redis import Redis

from app.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def normalize_text(text: str) -> str:
    """Normalize text for consistent cache keys: lowercase, collapse whitespace, strip."""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def cache_key(prefix: str, text: str) -> str:
    """Generate a Redis cache key from normalized text hash."""
    normalized = normalize_text(text)
    text_hash = hashlib.sha256(normalized.encode()).hexdigest()
    return f"{prefix}:{text_hash}"


def get_cached(key: str) -> dict | None:
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None


def set_cached(key: str, value: dict, ttl_seconds: int = 86400) -> None:
    redis_client.set(key, json.dumps(value), ex=ttl_seconds)
```

**Step 2: Create celery_worker.py**

```python
from celery import Celery

from app.config import settings

celery_app = Celery(
    "ai_job_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=2,
)

# Auto-discover tasks in ai_agent module
celery_app.autodiscover_tasks(["app.ai_agent"])
```

**Step 3: Write test for text normalization and cache key generation**

```python
# tests/test_redis.py
from app.redis import normalize_text, cache_key


def test_normalize_text():
    assert normalize_text("  Hello   World  ") == "hello world"
    assert normalize_text("Hello\n\tWorld") == "hello world"


def test_cache_key_same_for_equivalent_text():
    key1 = cache_key("jd", "Hello World")
    key2 = cache_key("jd", "  hello   world  ")
    assert key1 == key2


def test_cache_key_different_for_different_text():
    key1 = cache_key("jd", "Hello World")
    key2 = cache_key("jd", "Goodbye World")
    assert key1 != key2
```

**Step 4: Run tests**

Run: `pytest tests/test_redis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/redis.py celery_worker.py tests/test_redis.py
git commit -m "WIP: add Redis caching with text normalization and Celery worker config"
```

---

## Task 7: AI Agent Domain -- OpenAI Client, Prompts, Tasks

**Files:**
- Create: `app/ai_agent/__init__.py`
- Create: `app/ai_agent/openai_client.py`
- Create: `app/ai_agent/prompts.py`
- Create: `app/ai_agent/schemas.py`
- Create: `app/ai_agent/services.py`
- Create: `app/ai_agent/tasks.py`
- Create: `app/ai_agent/routes.py`
- Create: `tests/ai_agent/__init__.py`
- Create: `tests/ai_agent/test_prompts.py`
- Create: `tests/ai_agent/test_services.py`

**Step 1: Create prompts**

```python
# app/ai_agent/prompts.py

PARSE_JD_SYSTEM = """You are a senior technical recruiter. Parse the following job description and extract structured data. Return valid JSON only."""

PARSE_JD_USER = """Parse this job description and return JSON with these fields:
- required_skills: list of required technical skills
- preferred_skills: list of nice-to-have skills
- experience_level: string (junior/mid/senior/staff/lead)
- responsibilities: list of key responsibilities
- other_requirements: list of non-technical requirements (education, clearance, etc.)

Job Description:
{job_description}"""

SCORE_RESUME_SYSTEM = """You are a senior technical recruiter evaluating resume-to-job fit. Be objective and specific. Return valid JSON only."""

SCORE_RESUME_USER = """Score how well this resume matches the parsed job requirements.

Parsed Job Requirements:
{parsed_jd}

Resume Text:
{resume_text}

Return JSON with:
- overall_score: integer 0-100
- matched_skills: list of skills from the JD that the resume demonstrates
- missing_skills: list of required skills not found in the resume
- partial_skills: list of skills mentioned but with insufficient depth (include brief reason)
- summary: 2-3 sentence assessment"""

RECOMMEND_EDITS_SYSTEM = """You are a senior resume consultant. Give specific, actionable edit suggestions. Return valid JSON only."""

RECOMMEND_EDITS_USER = """Based on this resume's score against a job description, recommend specific edits to improve the fit.

Score Result:
{score_result}

Resume Text:
{resume_text}

Job Description Summary:
{parsed_jd}

Return a JSON list of objects, each with:
- section: which resume section to edit (e.g., "Summary", "Experience", "Skills", "Education")
- suggestion: specific actionable edit recommendation
- priority: "high", "medium", or "low"
"""
```

**Step 2: Write failing test for prompts**

```python
# tests/ai_agent/test_prompts.py
from app.ai_agent.prompts import PARSE_JD_USER, SCORE_RESUME_USER, RECOMMEND_EDITS_USER


def test_parse_jd_prompt_has_placeholder():
    assert "{job_description}" in PARSE_JD_USER


def test_score_resume_prompt_has_placeholders():
    assert "{parsed_jd}" in SCORE_RESUME_USER
    assert "{resume_text}" in SCORE_RESUME_USER


def test_recommend_edits_prompt_has_placeholders():
    assert "{score_result}" in RECOMMEND_EDITS_USER
    assert "{resume_text}" in RECOMMEND_EDITS_USER
    assert "{parsed_jd}" in RECOMMEND_EDITS_USER
```

**Step 3: Run tests**

Run: `pytest tests/ai_agent/test_prompts.py -v`
Expected: PASS

**Step 4: Create OpenAI client wrapper**

```python
# app/ai_agent/openai_client.py
import json
from datetime import date

from openai import OpenAI

from app.config import settings
from app.redis import get_cached, redis_client, set_cached

DAILY_COUNTER_KEY = "openai:daily_calls:{date}"


class OpenAIClient:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def _check_daily_limit(self) -> None:
        key = DAILY_COUNTER_KEY.format(date=date.today().isoformat())
        count = redis_client.get(key)
        current = int(count) if count else 0
        if current >= settings.openai_daily_call_limit:
            raise RuntimeError(
                f"Daily OpenAI call limit ({settings.openai_daily_call_limit}) reached. "
                "Try again tomorrow or increase OPENAI_DAILY_CALL_LIMIT."
            )

    def _increment_daily_counter(self) -> None:
        key = DAILY_COUNTER_KEY.format(date=date.today().isoformat())
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        pipe.execute()

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Send a chat completion request expecting JSON output."""
        self._check_daily_limit()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        self._increment_daily_counter()

        content = response.choices[0].message.content
        return json.loads(content)
```

**Step 5: Create AI schemas (AIScoreResult model)**

```python
# app/ai_agent/__init__.py
```

```python
# app/ai_agent/schemas.py
import enum
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AITaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIScoreResult(Base):
    __tablename__ = "ai_score_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skill_matches: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw_llm_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[AITaskStatus] = mapped_column(
        Enum(AITaskStatus), default=AITaskStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_score_app_resume_created", "application_id", "resume_id", created_at.desc()),
    )


# Pydantic response schemas
class AIScoreResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    resume_id: uuid.UUID
    overall_score: int | None
    skill_matches: dict | None
    recommendations: list | None
    model_used: str
    status: AITaskStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ScoreRequest(BaseModel):
    application_id: uuid.UUID
    resume_id: uuid.UUID
```

**Step 6: Create AI service**

```python
# app/ai_agent/services.py
import json

from app.ai_agent.openai_client import OpenAIClient
from app.ai_agent.prompts import (
    PARSE_JD_SYSTEM,
    PARSE_JD_USER,
    RECOMMEND_EDITS_SYSTEM,
    RECOMMEND_EDITS_USER,
    SCORE_RESUME_SYSTEM,
    SCORE_RESUME_USER,
)
from app.redis import cache_key, get_cached, set_cached


def parse_job_description(client: OpenAIClient, job_description: str) -> dict:
    """Parse a JD into structured data. Uses Redis cache."""
    key = cache_key("jd_parsed", job_description)
    cached = get_cached(key)
    if cached:
        return cached

    prompt = PARSE_JD_USER.format(job_description=job_description)
    result = client.chat_json(PARSE_JD_SYSTEM, prompt)
    set_cached(key, result)
    return result


def score_resume(client: OpenAIClient, parsed_jd: dict, resume_text: str) -> dict:
    """Score a resume against parsed JD requirements."""
    prompt = SCORE_RESUME_USER.format(
        parsed_jd=json.dumps(parsed_jd, indent=2),
        resume_text=resume_text,
    )
    return client.chat_json(SCORE_RESUME_SYSTEM, prompt)


def recommend_edits(
    client: OpenAIClient, parsed_jd: dict, resume_text: str, score_result: dict
) -> list:
    """Generate resume edit recommendations."""
    prompt = RECOMMEND_EDITS_USER.format(
        parsed_jd=json.dumps(parsed_jd, indent=2),
        resume_text=resume_text,
        score_result=json.dumps(score_result, indent=2),
    )
    result = client.chat_json(RECOMMEND_EDITS_SYSTEM, prompt)
    # The LLM may wrap the list in a key like "recommendations"
    if isinstance(result, dict):
        for key in ("recommendations", "edits", "suggestions"):
            if key in result and isinstance(result[key], list):
                return result[key]
        return [result]
    return result
```

**Step 7: Write test for AI service with mocked OpenAI**

```python
# tests/ai_agent/test_services.py
from unittest.mock import MagicMock, patch

from app.ai_agent.services import parse_job_description, score_resume, recommend_edits


@patch("app.ai_agent.services.get_cached", return_value=None)
@patch("app.ai_agent.services.set_cached")
def test_parse_job_description(mock_set_cached, mock_get_cached):
    mock_client = MagicMock()
    mock_client.chat_json.return_value = {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker"],
        "experience_level": "mid",
        "responsibilities": ["Build APIs"],
        "other_requirements": [],
    }

    result = parse_job_description(mock_client, "We need a Python dev...")
    assert result["required_skills"] == ["Python", "FastAPI"]
    mock_client.chat_json.assert_called_once()
    mock_set_cached.assert_called_once()


@patch("app.ai_agent.services.get_cached", return_value={"required_skills": ["Python"]})
def test_parse_job_description_uses_cache(mock_get_cached):
    mock_client = MagicMock()

    result = parse_job_description(mock_client, "We need a Python dev...")
    assert result["required_skills"] == ["Python"]
    mock_client.chat_json.assert_not_called()


def test_score_resume():
    mock_client = MagicMock()
    mock_client.chat_json.return_value = {
        "overall_score": 75,
        "matched_skills": ["Python"],
        "missing_skills": ["Kubernetes"],
        "partial_skills": [],
        "summary": "Good fit.",
    }

    result = score_resume(mock_client, {"required_skills": ["Python"]}, "I know Python...")
    assert result["overall_score"] == 75


def test_recommend_edits():
    mock_client = MagicMock()
    mock_client.chat_json.return_value = {
        "recommendations": [
            {"section": "Skills", "suggestion": "Add Docker", "priority": "high"}
        ]
    }

    result = recommend_edits(
        mock_client,
        {"required_skills": ["Docker"]},
        "I know Python...",
        {"overall_score": 60},
    )
    assert len(result) == 1
    assert result[0]["section"] == "Skills"
```

**Step 8: Run tests**

Run: `pytest tests/ai_agent/ -v`
Expected: PASS

**Step 9: Create Celery tasks**

```python
# app/ai_agent/tasks.py
import json
import asyncio

from sqlalchemy import select

from celery_worker import celery_app
from app.ai_agent.openai_client import OpenAIClient
from app.ai_agent.schemas import AIScoreResult, AITaskStatus
from app.ai_agent.services import parse_job_description, recommend_edits, score_resume
from app.applications.models import JobApplication
from app.config import settings
from app.database import async_session
from app.resumes.models import ResumeVersion


async def _run_scoring(score_result_id: str) -> None:
    async with async_session() as db:
        # Fetch the AIScoreResult
        result = await db.execute(
            select(AIScoreResult).where(AIScoreResult.id == score_result_id)
        )
        score_result = result.scalar_one()

        # Fetch application and resume
        app_result = await db.execute(
            select(JobApplication).where(JobApplication.id == score_result.application_id)
        )
        application = app_result.scalar_one()

        resume_result = await db.execute(
            select(ResumeVersion).where(ResumeVersion.id == score_result.resume_id)
        )
        resume = resume_result.scalar_one()

        try:
            client = OpenAIClient()

            # Step 1: Parse JD (cached)
            parsed_jd = parse_job_description(client, application.job_description)

            # Step 2: Score resume fit
            score_data = score_resume(client, parsed_jd, resume.extracted_text or "")

            # Step 3: Recommend edits
            recommendations = recommend_edits(
                client, parsed_jd, resume.extracted_text or "", score_data
            )

            # Save results
            score_result.overall_score = score_data.get("overall_score", 0)
            score_result.skill_matches = {
                "matched": score_data.get("matched_skills", []),
                "missing": score_data.get("missing_skills", []),
                "partial": score_data.get("partial_skills", []),
                "summary": score_data.get("summary", ""),
            }
            score_result.recommendations = recommendations
            score_result.raw_llm_response = json.dumps(
                {"score": score_data, "recommendations": recommendations}
            )
            score_result.model_used = settings.openai_model
            score_result.status = AITaskStatus.COMPLETED

        except Exception as e:
            score_result.status = AITaskStatus.FAILED
            score_result.raw_llm_response = str(e)

        await db.commit()


@celery_app.task(name="run_resume_scoring", bind=True, max_retries=1)
def run_resume_scoring(self, score_result_id: str) -> None:
    try:
        asyncio.run(_run_scoring(score_result_id))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5)
        # Final failure -- mark as failed
        asyncio.run(_mark_failed(score_result_id, str(exc)))


async def _mark_failed(score_result_id: str, error: str) -> None:
    async with async_session() as db:
        result = await db.execute(
            select(AIScoreResult).where(AIScoreResult.id == score_result_id)
        )
        score_result = result.scalar_one()
        score_result.status = AITaskStatus.FAILED
        score_result.raw_llm_response = error
        await db.commit()
```

**Step 10: Create AI routes**

```python
# app/ai_agent/routes.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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
    data: ScoreRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate application belongs to user
    app_result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == data.application_id, JobApplication.user_id == user.id
        )
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Validate resume belongs to user
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

    # Create pending result
    score_result = AIScoreResult(
        application_id=data.application_id,
        resume_id=data.resume_id,
        model_used=settings.openai_model,
        status=AITaskStatus.PENDING,
    )
    db.add(score_result)
    await db.commit()
    await db.refresh(score_result)

    # Dispatch Celery task
    run_resume_scoring.delay(str(score_result.id))

    return score_result


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
```

**Step 11: Register routes in main.py**

Add to `app/main.py`:
```python
from app.ai_agent.routes import router as ai_router
# inside create_app():
app.include_router(ai_router)
```

**Step 12: Commit**

```bash
git add app/ai_agent/ tests/ai_agent/
git commit -m "WIP: add AI agent domain -- OpenAI client, prompts, scoring pipeline, Celery tasks"
```

---

## Task 8: CSRF Middleware

**Files:**
- Create: `app/csrf.py`
- Create: `tests/test_csrf.py`

**Step 1: Write failing test**

```python
# tests/test_csrf.py
import secrets
from app.csrf import generate_csrf_token, validate_csrf_token


def test_generate_and_validate_csrf_token():
    token = generate_csrf_token()
    assert isinstance(token, str)
    assert len(token) == 64  # 32 bytes hex


def test_validate_csrf_token_rejects_bad_token():
    assert validate_csrf_token("good-token", "bad-token") is False


def test_validate_csrf_token_accepts_matching():
    token = generate_csrf_token()
    assert validate_csrf_token(token, token) is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_csrf.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement CSRF module**

```python
# app/csrf.py
import secrets

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def validate_csrf_token(session_token: str, form_token: str) -> bool:
    return secrets.compare_digest(session_token, form_token)


class CSRFMiddleware(BaseHTTPMiddleware):
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip CSRF for API-only routes (JSON content type)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            return await call_next(request)

        # Skip safe methods
        if request.method in self.SAFE_METHODS:
            # Ensure a CSRF token exists in session
            if "csrf_token" not in request.session:
                request.session["csrf_token"] = generate_csrf_token()
            return await call_next(request)

        # Validate CSRF token on unsafe methods with form data
        session_token = request.session.get("csrf_token", "")
        form = await request.form()
        form_token = form.get("csrf_token", "")

        if not validate_csrf_token(session_token, str(form_token)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )

        response = await call_next(request)
        return response
```

**Step 4: Run tests**

Run: `pytest tests/test_csrf.py -v`
Expected: PASS

**Step 5: Wire CSRF middleware into main.py**

Add to `app/main.py`:
```python
from starlette.middleware.sessions import SessionMiddleware
from app.csrf import CSRFMiddleware
from app.config import settings

# inside create_app():
app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret)
app.add_middleware(CSRFMiddleware)
```

**Step 6: Commit**

```bash
git add app/csrf.py tests/test_csrf.py app/main.py
git commit -m "WIP: add CSRF middleware for form submissions"
```

---

## Task 9: Alembic Migration -- Generate & Apply

**Step 1: Generate initial migration**

Run: `alembic revision --autogenerate -m "initial tables"`
Expected: Creates a migration file in `migrations/versions/`

**Step 2: Apply migration**

Run: `alembic upgrade head`
Expected: Creates tables: `users`, `job_applications`, `resume_versions`, `ai_score_results`

**Step 3: Verify tables exist**

Run: `docker exec -it <postgres-container> psql -U postgres -d job_tracker -c "\dt"`
Expected: Lists all 4 tables

**Step 4: Commit**

```bash
git add migrations/
git commit -m "WIP: add initial database migration"
```

---

## Task 10: Health Check -- DB & Redis Verification

**Files:**
- Modify: `app/main.py`
- Create: `tests/test_health.py`

**Step 1: Write failing test**

```python
# tests/test_health.py
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
```

**Step 2: Update health endpoint to check DB and Redis**

```python
# In app/main.py, replace the health endpoint:
from sqlalchemy import text

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    checks = {"database": "ok", "redis": "ok"}
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"
    try:
        redis_client.ping()
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
```

**Step 3: Run test**

Run: `pytest tests/test_health.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app/main.py tests/test_health.py
git commit -m "WIP: add health check with DB and Redis verification"
```

---

## Task 11: Jinja2 Templates -- Base Layout & Login

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/login.html`
- Create: `app/templates/dashboard.html`
- Modify: `app/main.py` (configure Jinja2)
- Modify: `app/auth/routes.py` (add template rendering)

**Step 1: Configure Jinja2 in main.py**

Add to `app/main.py`:
```python
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
```

**Step 2: Create base.html**

```html
<!-- app/templates/base.html -->
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Job Tracker{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <style>
        nav { padding: 1rem 2rem; }
        main { padding: 1rem 2rem; }
        .status-badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }
    </style>
</head>
<body>
    <nav>
        <ul>
            <li><strong>Job Tracker</strong></li>
        </ul>
        <ul>
            {% if user %}
            <li><a href="/dashboard">Dashboard</a></li>
            <li><a href="/applications">Applications</a></li>
            <li><a href="/resumes">Resumes</a></li>
            <li>
                <form method="POST" action="/auth/logout" style="display:inline">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                    <button type="submit" class="outline">Logout</button>
                </form>
            </li>
            {% endif %}
        </ul>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    {% block scripts %}{% endblock %}
</body>
</html>
```

**Step 3: Create login.html**

```html
<!-- app/templates/login.html -->
{% extends "base.html" %}
{% block title %}Login - Job Tracker{% endblock %}
{% block content %}
<article style="max-width: 400px; margin: 2rem auto;">
    <h2>Login</h2>
    {% if error %}
    <p style="color: red;">{{ error }}</p>
    {% endif %}
    <form method="POST" action="/auth/login">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" required>
        <label for="password">Password</label>
        <input type="password" id="password" name="password" required>
        <button type="submit">Login</button>
    </form>
</article>
{% endblock %}
```

**Step 4: Create dashboard.html**

```html
<!-- app/templates/dashboard.html -->
{% extends "base.html" %}
{% block title %}Dashboard - Job Tracker{% endblock %}
{% block content %}
<h2>Dashboard</h2>
<div class="grid">
    <article>
        <h3>Total Applications</h3>
        <p style="font-size: 2rem;">{{ stats.total }}</p>
    </article>
    <article>
        <h3>Active</h3>
        <p style="font-size: 2rem;">{{ stats.active }}</p>
    </article>
    <article>
        <h3>Offers</h3>
        <p style="font-size: 2rem;">{{ stats.offers }}</p>
    </article>
</div>

<h3>Recent Applications</h3>
<table>
    <thead>
        <tr>
            <th>Company</th>
            <th>Position</th>
            <th>Status</th>
            <th>Applied</th>
        </tr>
    </thead>
    <tbody>
        {% for app in recent %}
        <tr>
            <td><a href="/applications/{{ app.id }}">{{ app.company }}</a></td>
            <td>{{ app.position }}</td>
            <td><span class="status-badge">{{ app.status.value }}</span></td>
            <td>{{ app.applied_at.strftime('%Y-%m-%d') if app.applied_at else '-' }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

**Step 5: Add form-based login/logout to auth routes**

Update `app/auth/routes.py` to handle both JSON API and form submissions, and render the login template for GET requests.

**Step 6: Commit**

```bash
git add app/templates/ app/main.py app/auth/routes.py
git commit -m "WIP: add Jinja2 templates -- base layout, login page, dashboard"
```

---

## Task 12: Application & Resume UI Templates

**Files:**
- Create: `app/templates/applications/list.html`
- Create: `app/templates/applications/detail.html`
- Create: `app/templates/applications/create.html`
- Create: `app/templates/resumes/list.html`
- Create: `app/templates/ai_agent/results.html`
- Modify: `app/applications/routes.py` (add template views)
- Modify: `app/resumes/routes.py` (add template views)
- Modify: `app/ai_agent/routes.py` (add template views)

**Step 1: Create applications/list.html**

```html
{% extends "base.html" %}
{% block title %}Applications - Job Tracker{% endblock %}
{% block content %}
<h2>Applications</h2>
<a href="/applications/new" role="button">New Application</a>

<form method="GET" style="margin: 1rem 0;">
    <select name="status" onchange="this.form.submit()">
        <option value="">All Statuses</option>
        {% for s in statuses %}
        <option value="{{ s.value }}" {{ 'selected' if status_filter == s.value }}>{{ s.value }}</option>
        {% endfor %}
    </select>
</form>

<table>
    <thead>
        <tr>
            <th>Company</th>
            <th>Position</th>
            <th>Status</th>
            <th>Source</th>
            <th>Applied</th>
        </tr>
    </thead>
    <tbody>
        {% for app in applications %}
        <tr>
            <td><a href="/applications/{{ app.id }}">{{ app.company }}</a></td>
            <td>{{ app.position }}</td>
            <td>{{ app.status.value }}</td>
            <td>{{ app.source or '-' }}</td>
            <td>{{ app.applied_at.strftime('%Y-%m-%d') if app.applied_at else '-' }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

**Step 2: Create applications/create.html and applications/detail.html**

Standard Jinja2 forms with all JobApplication fields, CSRF tokens, and status dropdowns.

**Step 3: Create resumes/list.html**

Upload form (PDF file input + version label) and table listing existing resumes with download/delete actions.

**Step 4: Create ai_agent/results.html**

Display score (0-100 with visual bar), skill matches (matched/missing/partial lists), and recommendations table.

Include a small JS block for polling `/ai/score/{score_id}` when status is PENDING:
```javascript
{% if score.status.value == "PENDING" %}
<script>
    const scoreId = "{{ score.id }}";
    const poll = setInterval(async () => {
        const res = await fetch(`/ai/score/${scoreId}`);
        const data = await res.json();
        if (data.status !== "PENDING") {
            clearInterval(poll);
            location.reload();
        }
    }, 3000);
</script>
{% endif %}
```

**Step 5: Add template-rendering view routes alongside API routes**

Each domain's `routes.py` gets additional GET endpoints that render templates (e.g., `GET /applications` renders the list template, `GET /applications/new` renders the create form).

**Step 6: Commit**

```bash
git add app/templates/ app/applications/routes.py app/resumes/routes.py app/ai_agent/routes.py
git commit -m "WIP: add application, resume, and AI result UI templates"
```

---

## Task 13: Integration Test Setup

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_integration.py`

**Step 1: Create test conftest with async DB fixtures**

```python
# tests/conftest.py
import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.models import User
from app.auth.services import hash_password
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_tracker_test"

engine = create_async_engine(TEST_DATABASE_URL)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(id=uuid4(), username="testuser", password_hash=hash_password("testpass"))
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

**Step 2: Write integration test for login flow**

```python
# tests/test_integration.py
import pytest


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    response = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    response = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "wrong"},
    )
    assert response.status_code == 401
```

**Step 3: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/
git commit -m "WIP: add integration test setup with async DB fixtures and login tests"
```

---

## Task 14: Final Assembly & Smoke Test

**Step 1: Update app/main.py with all routers and middleware**

Ensure `app/main.py` includes:
- All 4 domain routers (auth, applications, resumes, ai_agent)
- SessionMiddleware + CSRFMiddleware
- Jinja2 template configuration
- Health endpoint with DB + Redis checks

**Step 2: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

**Step 3: Manual smoke test**

```bash
# Terminal 1: Start services
docker-compose up -d

# Terminal 2: Start app
uvicorn app.main:app --reload

# Terminal 3: Start Celery worker
celery -A celery_worker worker --loglevel=info --concurrency=2

# Terminal 4: Create user and test
python -m app.cli create-user --username raza --password yourpassword
curl http://localhost:8000/health
# Open http://localhost:8000/auth/login in browser
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "Complete AI Job Application Tracker -- all domains, UI, AI scoring pipeline"
```

---

## Execution Checklist

| Task | Description | Est. Steps |
|------|-------------|------------|
| 1 | Project skeleton & config | 9 |
| 2 | Database setup & Alembic | 5 |
| 3 | Auth domain (model, JWT, CLI) | 11 |
| 4 | Applications domain (model, CRUD) | 7 |
| 5 | Resumes domain (model, upload, PDF) | 7 |
| 6 | Redis setup & Celery worker | 5 |
| 7 | AI agent domain (OpenAI, prompts, tasks) | 12 |
| 8 | CSRF middleware | 6 |
| 9 | Alembic migration | 4 |
| 10 | Health check (DB + Redis) | 4 |
| 11 | Jinja2 templates (base, login, dashboard) | 6 |
| 12 | Application & resume UI templates | 6 |
| 13 | Integration test setup | 4 |
| 14 | Final assembly & smoke test | 4 |
