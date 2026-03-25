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
