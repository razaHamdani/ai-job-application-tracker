# AI Job Application Tracker -- System Design

## Overview

Personal, login-protected tool for tracking job applications with AI-powered resume scoring. Single user, server-rendered UI, background AI processing.

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL (async via SQLAlchemy + asyncpg)
- **Cache / Broker**: Redis (LLM response cache + Celery task broker)
- **LLM**: OpenAI GPT-4 (JSON mode, temperature 0.2)
- **Migrations**: Alembic
- **UI**: Jinja2 templates + Pico CSS
- **PDF Extraction**: pypdf
- **Auth**: JWT in HTTP-only SameSite=Strict cookie + CSRF tokens
- **Background Tasks**: Celery

## Architecture

Modular monolith with domain packages. Each domain owns its models, routes, services, and schemas.

```
Routes (API + Jinja2) -> Services -> Repositories -> PostgreSQL
                              |
                              +-> AI Service -> OpenAI
                              +-> Celery Tasks -> Redis (broker + cache)
```

## Project Structure

```
ai-job-application-tracker/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app factory, CSRF middleware
│   ├── config.py                # Settings via pydantic-settings (refuses to start on placeholder secrets)
│   ├── database.py              # SQLAlchemy async engine + session
│   ├── redis.py                 # Redis client setup
│   ├── dependencies.py          # Shared deps: get_db, get_current_user
│   │
│   ├── auth/
│   │   ├── models.py            # User model
│   │   ├── routes.py            # login, logout (no registration endpoint)
│   │   ├── services.py          # password hashing, JWT
│   │   └── schemas.py
│   │
│   ├── applications/
│   │   ├── models.py            # JobApplication
│   │   ├── routes.py            # CRUD endpoints + Jinja2 views
│   │   ├── services.py          # Business logic
│   │   └── schemas.py
│   │
│   ├── resumes/
│   │   ├── models.py            # ResumeVersion
│   │   ├── routes.py            # Upload, list, download
│   │   ├── services.py          # PDF text extraction (pypdf)
│   │   └── schemas.py
│   │
│   ├── ai_agent/
│   │   ├── routes.py            # Trigger scoring, get results
│   │   ├── services.py          # Orchestrates AI operations
│   │   ├── tasks.py             # Celery tasks
│   │   ├── prompts.py           # LLM prompt templates
│   │   ├── schemas.py           # Score results, recommendations
│   │   └── openai_client.py     # OpenAI API wrapper with cost tracking
│   │
│   ├── cli.py                   # CLI commands: create-user
│   │
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── applications/
│       ├── resumes/
│       └── ai_agent/
│
├── alembic.ini                  # At project root (not inside migrations/)
├── migrations/
│   └── versions/
│
├── uploads/                     # PDF storage (gitignored)
├── tests/
├── celery_worker.py
├── requirements.txt
├── .env.example
└── docker-compose.yml           # PostgreSQL + Redis for local dev
```

## Data Models

### User

| Column        | Type     | Notes                          |
|---------------|----------|--------------------------------|
| id            | UUID PK  |                                |
| username      | String   | Unique                         |
| password_hash | String   |                                |
| created_at    | DateTime |                                |

### JobApplication

| Column          | Type     | Notes                          |
|-----------------|----------|--------------------------------|
| id              | UUID PK  |                                |
| user_id         | FK(User) |                                |
| company         | String   |                                |
| position        | String   |                                |
| url             | String   | Nullable. Link to job posting  |
| job_description | Text     |                                |
| status          | Enum     | DRAFT, APPLIED, SCREENING, INTERVIEWING, OFFER, REJECTED, WITHDRAWN, GHOSTED |
| applied_at      | DateTime | Nullable (DRAFT has no date)   |
| source          | String   | LinkedIn, Indeed, etc.         |
| notes           | Text     | Free-text for recruiter comms, observations |
| created_at      | DateTime |                                |
| updated_at      | DateTime |                                |

### ResumeVersion

| Column         | Type     | Notes                          |
|----------------|----------|--------------------------------|
| id             | UUID PK  |                                |
| user_id        | FK(User) |                                |
| filename       | String   | Original filename (display only) |
| file_path      | String   | UUID-generated name on disk (prevents path traversal) |
| extracted_text | Text     | Plain text from PDF for AI     |
| version_label  | String   | e.g. "Backend Engineer v2"     |
| created_at     | DateTime |                                |

On delete: application-level cleanup removes file from disk.

### AIScoreResult

| Column           | Type              | Notes                          |
|------------------|-------------------|--------------------------------|
| id               | UUID PK           |                                |
| application_id   | FK(JobApplication) | ondelete=CASCADE              |
| resume_id        | FK(ResumeVersion)  | ondelete=CASCADE              |
| overall_score    | Integer           | 0-100                          |
| skill_matches    | JSON              | matched/missing/partial skills |
| recommendations  | JSON              | suggested resume edits         |
| raw_llm_response | Text              | Full LLM output for debugging  |
| model_used       | String            | e.g. "gpt-4o"                  |
| status           | Enum              | PENDING, COMPLETED, FAILED     |
| created_at       | DateTime          |                                |

Index on `(application_id, resume_id, created_at DESC)` for fetching latest result.

Multiple scores per application+resume pair allowed (re-scoring creates new rows).

#### skill_matches example

```json
{
  "matched": ["Python", "FastAPI", "PostgreSQL"],
  "missing": ["Kubernetes", "Terraform"],
  "partial": ["AWS (mentioned but limited depth)"]
}
```

#### recommendations example

```json
[
  {"section": "Experience", "suggestion": "Quantify your FastAPI project -- add throughput/scale numbers"},
  {"section": "Skills", "suggestion": "Add 'CI/CD' -- your experience section implies it but skills section omits it"},
  {"section": "Summary", "suggestion": "Lead with backend/infrastructure focus to match this role"}
]
```

## AI Agent Design

### Operations (all run as Celery background tasks)

**1. Parse Job Description**
- Input: `job_description` text from a JobApplication
- LLM extracts: required skills, experience level, responsibilities, nice-to-haves
- Cached in Redis keyed by normalized text hash (strip, collapse whitespace, lowercase before hashing)
- Same JD across multiple resume scores = one parse call

**2. Score Resume Fit**
- Input: ResumeVersion.extracted_text + parsed JD from step 1
- Output: overall_score (0-100) + skill_matches JSON
- Not cached (different resume = different score)

**3. Recommend Resume Edits**
- Input: resume + JD + score result from step 2
- Output: recommendations JSON with section-level edit suggestions

### Flow

```
User clicks "Score Resume" on an application
        |
        v
    API validates inputs, checks rate limit
        |
        v
    Celery task queued (returns task_id)
        |
        v
    Worker: parse JD (cached?) -> score fit -> generate recommendations
        |
        v
    Result saved to AIScoreResult (status=COMPLETED or FAILED)
        |
        v
    UI polls /ai/status/{task_id} until complete, then displays results
```

### Prompt Strategy
- Separate prompt templates per operation in `ai_agent/prompts.py`
- System prompt: "senior technical recruiter"
- OpenAI JSON mode for structured output
- Temperature: 0.2 for consistent scoring

### Cost Controls
- Max concurrent Celery AI tasks: 2
- Daily API call cap checked before dispatching (configurable via env)
- Token usage logged per request for monitoring

## Auth

- No registration endpoint. User created via CLI: `python -m app.cli create-user --username raza --password ****`
- Login via username + password, returns JWT in HTTP-only cookie with `SameSite=Strict`
- CSRF token middleware: every Jinja2 form includes a hidden CSRF token field, server validates on POST/PUT/DELETE
- `get_current_user` FastAPI dependency protects all routes
- `config.py` validates JWT_SECRET at startup -- refuses to start if it matches the placeholder value

## UI Pages

| Page                 | Purpose                                              |
|----------------------|------------------------------------------------------|
| Login                | Username + password form                             |
| Dashboard            | Summary stats: total apps, by status, recent activity |
| Applications list    | Table with filters by status, search by company/position |
| Application detail   | View/edit form, trigger AI scoring from here          |
| Resumes list         | Upload new PDF, list versions with labels             |
| AI Results           | Score breakdown, skill matches, recommendations       |

- Server-rendered HTML via Jinja2
- Pico CSS (classless, ~10KB)
- Minimal JS only where needed: polling for AI task status, file upload handling

## Infrastructure

### Local Development
- `docker-compose.yml` runs PostgreSQL + Redis only
- App runs via `uvicorn app.main:app --reload` for hot reload
- `.env.example` with all config keys and generation instructions for secrets

### Health Check
- `GET /health` endpoint checks DB and Redis connectivity, returns status JSON

### File Uploads
- PDF only, max 5MB
- Stored in `uploads/` with UUID-generated filenames
- `uploads/` is gitignored

### Error Handling
- Global exception handler: JSON for API routes, rendered error page for UI routes
- OpenAI API failures: retry once, then save `status=FAILED` on AIScoreResult
- File upload validation: reject non-PDF, reject >5MB

## Testing

- `pytest` + `pytest-asyncio`
- Separate test PostgreSQL database (configured via env)
- OpenAI client mocked in all tests (no real API calls)
- Celery: `task_always_eager = True` for synchronous task execution in tests

## Dependencies

```
fastapi
uvicorn
sqlalchemy[asyncio]
asyncpg
alembic
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
celery[redis]
redis
openai
pypdf
jinja2
python-multipart
httpx
pytest
pytest-asyncio
```
