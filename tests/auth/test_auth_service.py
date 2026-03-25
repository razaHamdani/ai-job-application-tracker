from app.auth.services import hash_password, verify_password, create_access_token, decode_access_token


def test_hash_and_verify_password():
    password = "testpass123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_create_and_decode_token():
    user_id = "test-user-id"
    token = create_access_token(user_id)
    payload = decode_access_token(token)
    assert payload["sub"] == user_id
