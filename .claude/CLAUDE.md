# AI Job Application Tracker

AI-powered job application tracking and management tool with resume scoring.

**Tech Stack**: Python, FastAPI, PostgreSQL, Redis, Celery, OpenAI, Alembic, Jinja2, Pico CSS

## Architecture

Modular monolith with domain packages: `auth`, `applications`, `resumes`, `ai_agent`.

```
app/
  auth/         -- User model, JWT auth, login/logout
  applications/ -- JobApplication CRUD
  resumes/      -- ResumeVersion upload, PDF text extraction
  ai_agent/     -- OpenAI scoring pipeline, Celery tasks
  templates/    -- Jinja2 server-rendered UI
```

- Server-rendered HTML via Jinja2 + Pico CSS
- JWT in httponly SameSite=Strict cookie
- CSRF middleware on all form POSTs
- Background AI tasks via Celery + Redis broker
- No registration endpoint -- user created via CLI

## Development

```bash
# Start services
docker-compose up -d

# Install deps
pip install -r requirements.txt

# Copy env and configure
cp .env.example .env
# Edit .env: set JWT_SECRET, OPENAI_API_KEY

# Run migrations
alembic revision --autogenerate -m "initial tables"
alembic upgrade head

# Create user
python -m app.cli create-user --username <name> --password <pass>

# Start app
uvicorn app.main:app --reload

# Start Celery worker
celery -A celery_worker worker --loglevel=info --concurrency=2
```

## Testing

```bash
pytest -v                     # all tests
pytest tests/auth/ -v         # auth tests only
pytest tests/ai_agent/ -v     # ai agent tests only
```

- Test DB: `job_tracker_test` (configure in tests/conftest.py)
- OpenAI client mocked in all tests
- Celery: `task_always_eager = True` for sync execution in tests

## Conventions

- Import settings: `from app.config import settings`
- Import DB session: `from app.database import get_db`
- All models use UUID primary keys
- Foreign keys include `ondelete="CASCADE"` and `index=True`
- Domain structure: `models.py`, `schemas.py`, `services.py`, `routes.py`
- Design doc: `docs/plans/2026-03-24-system-design.md`
- Implementation plan: `docs/plans/2026-03-24-implementation-plan.md`
