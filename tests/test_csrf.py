from app.csrf import generate_csrf_token, validate_csrf_token


def test_generate_csrf_token():
    token = generate_csrf_token()
    assert isinstance(token, str)
    assert len(token) == 64  # 32 bytes hex


def test_validate_csrf_token_rejects_bad_token():
    assert validate_csrf_token("good-token", "bad-token") is False


def test_validate_csrf_token_accepts_matching():
    token = generate_csrf_token()
    assert validate_csrf_token(token, token) is True
