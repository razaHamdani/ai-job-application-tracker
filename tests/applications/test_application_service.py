from app.applications.schemas import ApplicationCreate, ApplicationStatus


def test_application_create_schema():
    data = ApplicationCreate(
        company="Acme Corp",
        position="Backend Engineer",
        job_description="We need a Python dev...",
        status=ApplicationStatus.DRAFT,
        source="LinkedIn",
    )
    assert data.company == "Acme Corp"
    assert data.status == ApplicationStatus.DRAFT
    assert data.url is None
