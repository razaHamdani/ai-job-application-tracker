from app.ai_agent.prompts import PARSE_JD_USER, SCORE_RESUME_USER, RECOMMEND_EDITS_USER


def test_parse_jd_prompt_has_placeholder():
    assert "{job_description}" in PARSE_JD_USER


def test_score_resume_prompt_has_placeholders():
    assert "{parsed_jd}" in SCORE_RESUME_USER
    assert "{resume_text}" in SCORE_RESUME_USER


def test_recommend_edits_prompt_has_placeholders():
    assert "{score_result}" in RECOMMEND_EDITS_USER
    assert "{resume_text}" in RECOMMEND_EDITS_USER
    assert "{parsed_jd}" in RECOMMEND_EDITS_USER
