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
