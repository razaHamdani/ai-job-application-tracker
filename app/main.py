from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="AI Job Application Tracker")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
