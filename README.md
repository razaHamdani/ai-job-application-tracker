# AI Job Application Tracker

AI-powered job application tracking and management tool with resume scoring. Track applications, upload resume versions, and get AI-powered resume-to-JD fit analysis with actionable edit recommendations.

## Architecture

Modular monolith with domain packages:

```
app/
  auth/         -- User model, JWT auth (httponly cookie), login/logout
  applications/ -- JobApplication CRUD with status tracking
  resumes/      -- ResumeVersion upload, PDF text extraction (pypdf)
  ai_agent/     -- OpenAI scoring pipeline, Celery background tasks
  templates/    -- Jinja2 server-rendered UI (Pico CSS)
  csrf.py       -- CSRF middleware for form POSTs
  main.py       -- FastAPI app factory, middleware, routers
  config.py     -- pydantic-settings configuration
  database.py   -- Async SQLAlchemy engine + session
  redis.py      -- Redis client, caching utilities
  cli.py        -- User creation CLI
```

- Server-rendered HTML via Jinja2 + Pico CSS (classless styling)
- JWT authentication in httponly SameSite=Strict cookies
- CSRF middleware on all form POSTs
- Background AI tasks via Celery + Redis broker
- No registration endpoint -- users created via CLI
- All models use UUID primary keys

## Tech Stack

- **Language**: Python 3.10+
- **Framework**: FastAPI (async)
- **Database**: PostgreSQL (asyncpg driver, SQLAlchemy 2.0 async ORM)
- **Migrations**: Alembic (autogenerate from models)
- **Cache / Broker**: Redis
- **Task Queue**: Celery
- **AI**: OpenAI (GPT-4o, JSON mode)
- **PDF Parsing**: pypdf
- **Auth**: JWT (python-jose) + bcrypt (passlib)
- **UI**: Jinja2 templates + Pico CSS

## Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- Docker & Docker Compose (recommended for services)

## Quick Start

```bash
# Clone the repo
git clone git@github.com:razaHamdani/ai-job-application-tracker.git
cd ai-job-application-tracker

# Start PostgreSQL + Redis
docker-compose up -d

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env and configure
cp .env.example .env
# Edit .env: set JWT_SECRET, OPENAI_API_KEY

# Run migrations
alembic upgrade head

# Create a user (no registration endpoint)
python -m app.cli create-user --username <name> --password <pass>

# Start the app
uvicorn app.main:app --reload

# Start Celery worker (separate terminal)
celery -A celery_worker worker --loglevel=info --concurrency=2
```

## Configuration

Copy `.env.example` to `.env` and set the required values:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `REDIS_URL` | No | Redis URL (default: `redis://localhost:6379/0`) |
| `JWT_SECRET` | Yes | Secret key for JWT signing (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_MODEL` | No | Model to use (default: `gpt-4o`) |
| `OPENAI_DAILY_CALL_LIMIT` | No | Daily API call limit (default: `100`) |

## Testing

```bash
pytest -v                     # all tests
pytest tests/auth/ -v         # auth tests only
pytest tests/ai_agent/ -v     # ai agent tests only
```

- Test DB: `job_tracker_test` (configure in `tests/conftest.py`)
- OpenAI client mocked in all tests
- Celery: `task_always_eager = True` for sync execution in tests
- `asyncio_mode = auto` in `pytest.ini`

## Project Structure

```
ai-job-application-tracker/
├── app/
│   ├── auth/              # User model, JWT auth, login/logout
│   ├── applications/      # JobApplication CRUD
│   ├── resumes/           # Resume upload, PDF extraction
│   ├── ai_agent/          # OpenAI scoring, Celery tasks
│   ├── templates/         # Jinja2 HTML templates
│   ├── main.py            # FastAPI app + middleware
│   ├── config.py          # Settings (pydantic-settings)
│   ├── database.py        # Async SQLAlchemy setup
│   ├── redis.py           # Redis client + caching
│   ├── csrf.py            # CSRF middleware
│   ├── dependencies.py    # Auth dependency (get_current_user)
│   └── cli.py             # User creation CLI
├── migrations/            # Alembic migrations
├── tests/                 # pytest test suite
├── docs/plans/            # Design docs + implementation plan
├── celery_worker.py       # Celery app configuration
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── pytest.ini
```
