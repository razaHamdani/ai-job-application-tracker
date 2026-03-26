from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.applications.routes import router as applications_router
from app.auth.routes import router as auth_router
from app.ai_agent.routes import router as ai_router
from app.config import settings
from app.csrf import CSRFMiddleware
from app.database import get_db
from app.redis import redis_client
from app.resumes.routes import router as resumes_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Job Application Tracker")

    app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret)
    app.add_middleware(CSRFMiddleware)

    app.include_router(auth_router)
    app.include_router(applications_router)
    app.include_router(resumes_router)
    app.include_router(ai_router)

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

    return app


app = create_app()
