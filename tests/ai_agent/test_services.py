from unittest.mock import MagicMock, patch

from app.ai_agent.services import parse_job_description, score_resume, recommend_edits


@patch("app.ai_agent.services.get_cached", return_value=None)
@patch("app.ai_agent.services.set_cached")
def test_parse_job_description(mock_set_cached, mock_get_cached):
    mock_client = MagicMock()
    mock_client.chat_json.return_value = {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker"],
        "experience_level": "mid",
        "responsibilities": ["Build APIs"],
        "other_requirements": [],
    }

    result = parse_job_description(mock_client, "We need a Python dev...")
    assert result["required_skills"] == ["Python", "FastAPI"]
    mock_client.chat_json.assert_called_once()
    mock_set_cached.assert_called_once()


@patch("app.ai_agent.services.get_cached", return_value={"required_skills": ["Python"]})
def test_parse_job_description_uses_cache(mock_get_cached):
    mock_client = MagicMock()

    result = parse_job_description(mock_client, "We need a Python dev...")
    assert result["required_skills"] == ["Python"]
    mock_client.chat_json.assert_not_called()


def test_score_resume():
    mock_client = MagicMock()
    mock_client.chat_json.return_value = {
        "overall_score": 75,
        "matched_skills": ["Python"],
        "missing_skills": ["Kubernetes"],
        "partial_skills": [],
        "summary": "Good fit.",
    }

    result = score_resume(mock_client, {"required_skills": ["Python"]}, "I know Python...")
    assert result["overall_score"] == 75


def test_recommend_edits():
    mock_client = MagicMock()
    mock_client.chat_json.return_value = {
        "recommendations": [
            {"section": "Skills", "suggestion": "Add Docker", "priority": "high"}
        ]
    }

    result = recommend_edits(
        mock_client,
        {"required_skills": ["Docker"]},
        "I know Python...",
        {"overall_score": 60},
    )
    assert len(result) == 1
    assert result[0]["section"] == "Skills"
