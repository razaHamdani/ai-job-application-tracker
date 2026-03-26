import json
from datetime import date

from openai import OpenAI

from app.config import settings
from app.redis import redis_client

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
