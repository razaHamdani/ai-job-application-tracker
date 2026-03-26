PARSE_JD_SYSTEM = """You are a senior technical recruiter. Parse the following job description and extract structured data. Return valid JSON only."""

PARSE_JD_USER = """Parse this job description and return JSON with these fields:
- required_skills: list of required technical skills
- preferred_skills: list of nice-to-have skills
- experience_level: string (junior/mid/senior/staff/lead)
- responsibilities: list of key responsibilities
- other_requirements: list of non-technical requirements (education, clearance, etc.)

Job Description:
{job_description}"""

SCORE_RESUME_SYSTEM = """You are a senior technical recruiter evaluating resume-to-job fit. Be objective and specific. Return valid JSON only."""

SCORE_RESUME_USER = """Score how well this resume matches the parsed job requirements.

Parsed Job Requirements:
{parsed_jd}

Resume Text:
{resume_text}

Return JSON with:
- overall_score: integer 0-100
- matched_skills: list of skills from the JD that the resume demonstrates
- missing_skills: list of required skills not found in the resume
- partial_skills: list of skills mentioned but with insufficient depth (include brief reason)
- summary: 2-3 sentence assessment"""

RECOMMEND_EDITS_SYSTEM = """You are a senior resume consultant. Give specific, actionable edit suggestions. Return valid JSON only."""

RECOMMEND_EDITS_USER = """Based on this resume's score against a job description, recommend specific edits to improve the fit.

Score Result:
{score_result}

Resume Text:
{resume_text}

Job Description Summary:
{parsed_jd}

Return a JSON list of objects, each with:
- section: which resume section to edit (e.g., "Summary", "Experience", "Skills", "Education")
- suggestion: specific actionable edit recommendation
- priority: "high", "medium", or "low"
"""
