"""Consistent API error responses; no secrets or raw stack traces are exposed."""
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        self.message = message
        if status_code:
            self.status_code = status_code
        if code:
            self.code = code
        super().__init__(message)


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class InvalidInput(AppError):
    status_code = 400
    code = "invalid_input"


class UnprocessableData(AppError):
    status_code = 422
    code = "unprocessable_data"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # Intentionally generic: never leak internals.
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Unexpected server error."}},
    )
