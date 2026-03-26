import asyncio
import json

from sqlalchemy import select

from app.ai_agent.openai_client import OpenAIClient
from app.ai_agent.schemas import AIScoreResult, AITaskStatus
from app.ai_agent.services import parse_job_description, recommend_edits, score_resume
from app.applications.models import JobApplication
from app.config import settings
from app.database import async_session
from app.resumes.models import ResumeVersion
from celery_worker import celery_app


async def _run_scoring(score_result_id: str) -> None:
    async with async_session() as db:
        result = await db.execute(
            select(AIScoreResult).where(AIScoreResult.id == score_result_id)
        )
        score_result = result.scalar_one()

        app_result = await db.execute(
            select(JobApplication).where(JobApplication.id == score_result.application_id)
        )
        application = app_result.scalar_one()

        resume_result = await db.execute(
            select(ResumeVersion).where(ResumeVersion.id == score_result.resume_id)
        )
        resume = resume_result.scalar_one()

        try:
            client = OpenAIClient()

            parsed_jd = parse_job_description(client, application.job_description)
            score_data = score_resume(client, parsed_jd, resume.extracted_text or "")
            recommendations = recommend_edits(
                client, parsed_jd, resume.extracted_text or "", score_data
            )

            score_result.overall_score = score_data.get("overall_score", 0)
            score_result.skill_matches = {
                "matched": score_data.get("matched_skills", []),
                "missing": score_data.get("missing_skills", []),
                "partial": score_data.get("partial_skills", []),
                "summary": score_data.get("summary", ""),
            }
            score_result.recommendations = recommendations
            score_result.raw_llm_response = json.dumps(
                {"score": score_data, "recommendations": recommendations}
            )
            score_result.model_used = settings.openai_model
            score_result.status = AITaskStatus.COMPLETED

        except Exception as e:
            score_result.status = AITaskStatus.FAILED
            score_result.raw_llm_response = str(e)

        await db.commit()


@celery_app.task(name="run_resume_scoring", bind=True, max_retries=1)
def run_resume_scoring(self, score_result_id: str) -> None:
    try:
        asyncio.run(_run_scoring(score_result_id))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5)
        asyncio.run(_mark_failed(score_result_id, str(exc)))


async def _mark_failed(score_result_id: str, error: str) -> None:
    async with async_session() as db:
        result = await db.execute(
            select(AIScoreResult).where(AIScoreResult.id == score_result_id)
        )
        score_result = result.scalar_one()
        score_result.status = AITaskStatus.FAILED
        score_result.raw_llm_response = error
        await db.commit()
