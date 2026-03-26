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
    key = cache_key("jd_parsed", job_description)
    cached = get_cached(key)
    if cached:
        return cached

    prompt = PARSE_JD_USER.format(job_description=job_description)
    result = client.chat_json(PARSE_JD_SYSTEM, prompt)
    set_cached(key, result)
    return result


def score_resume(client: OpenAIClient, parsed_jd: dict, resume_text: str) -> dict:
    prompt = SCORE_RESUME_USER.format(
        parsed_jd=json.dumps(parsed_jd, indent=2),
        resume_text=resume_text,
    )
    return client.chat_json(SCORE_RESUME_SYSTEM, prompt)


def recommend_edits(
    client: OpenAIClient, parsed_jd: dict, resume_text: str, score_result: dict
) -> list:
    prompt = RECOMMEND_EDITS_USER.format(
        parsed_jd=json.dumps(parsed_jd, indent=2),
        resume_text=resume_text,
        score_result=json.dumps(score_result, indent=2),
    )
    result = client.chat_json(RECOMMEND_EDITS_SYSTEM, prompt)
    if isinstance(result, dict):
        for key in ("recommendations", "edits", "suggestions"):
            if key in result and isinstance(result[key], list):
                return result[key]
        return [result]
    return result
