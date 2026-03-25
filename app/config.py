from functools import lru_cache

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
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if self.openai_api_key == "sk-your-key-here":
            raise ValueError("OPENAI_API_KEY is still a placeholder.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
