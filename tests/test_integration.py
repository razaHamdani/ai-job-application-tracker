import pytest


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    response = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    response = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "wrong"},
    )
    assert response.status_code == 401
