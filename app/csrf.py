import secrets

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def validate_csrf_token(session_token: str, form_token: str) -> bool:
    return secrets.compare_digest(session_token, form_token)


class CSRFMiddleware(BaseHTTPMiddleware):
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip CSRF for API-only routes (JSON content type)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            return await call_next(request)

        # Skip safe methods
        if request.method in self.SAFE_METHODS:
            # Ensure a CSRF token exists in session
            if "csrf_token" not in request.session:
                request.session["csrf_token"] = generate_csrf_token()
            return await call_next(request)

        # Validate CSRF token on unsafe methods with form data
        session_token = request.session.get("csrf_token", "")
        form = await request.form()
        form_token = form.get("csrf_token", "")

        if not validate_csrf_token(session_token, str(form_token)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )

        response = await call_next(request)
        return response
