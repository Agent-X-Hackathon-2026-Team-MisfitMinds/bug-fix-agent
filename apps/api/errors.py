"""Standard error format: {"error": {"code", "message", "details"}}."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str = "Something went wrong",
                 details: list[Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class ValidationFailed(AppError):
    status_code, code = 400, "VALIDATION_ERROR"


class Unauthorized(AppError):
    status_code, code = 401, "UNAUTHORIZED"


class Forbidden(AppError):
    status_code, code = 403, "FORBIDDEN"


class NotFoundError(AppError):
    status_code, code = 404, "NOT_FOUND"


class ConflictError(AppError):
    status_code, code = 409, "CONFLICT"


class RateLimited(AppError):
    status_code, code = 429, "RATE_LIMITED"

    def __init__(self, retry_after: int, message: str = "Too many requests") -> None:
        super().__init__(message)
        self.retry_after = retry_after


def _body(code: str, message: str, details: list[Any]) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = None
        if isinstance(exc, RateLimited):
            headers = {"Retry-After": str(exc.retry_after)}
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in error["loc"]), "rule": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=_body("VALIDATION_ERROR", "Invalid request", details),
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_body(
                "INTERNAL_ERROR",
                "Something went wrong - please try again",
                [],
            ),
        )
