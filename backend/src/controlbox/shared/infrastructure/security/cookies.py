from fastapi import Request, Response

from controlbox.config.settings import Settings

REFRESH_COOKIE_NAME = "cb_refresh"
ACCESS_COOKIE_NAME = "cb_access"
CSRF_COOKIE_NAME = "cb_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def set_access_cookie(
    response: Response,
    access_token: str,
    settings: Settings,
    max_age_seconds: int | None = None,
) -> None:
    max_age = max_age_seconds if isinstance(max_age_seconds, int) and max_age_seconds > 0 else settings.jwt_access_token_expire_minutes * 60
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.use_secure_cookies,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_access_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.use_secure_cookies,
        samesite="lax",
    )


def get_access_token_from_request(request: Request) -> str | None:
    return request.cookies.get(ACCESS_COOKIE_NAME)


def set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.use_secure_cookies,
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        path="/api/v1/identity/auth",
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/identity/auth",
        httponly=True,
        secure=settings.use_secure_cookies,
        samesite="lax",
    )
    clear_access_cookie(response, settings)


def get_refresh_token_from_request(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE_NAME)


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=settings.use_secure_cookies,
        samesite="lax",
        max_age=3600,
        path="/",
    )
