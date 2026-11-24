"""Business exceptions and their translation to HTTP errors."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class: carries a machine-readable code and a human message."""
    status_code = 500

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class RuleViolation(AppError):
    """A business rule or validation is broken (hours, duration, limit...)."""
    status_code = 422


class NotFound(AppError):
    """The room or booking does not exist."""
    status_code = 404


class Conflict(AppError):
    """The request conflicts with the current state (overlap, already started)."""
    status_code = 409


class Forbidden(AppError):
    """The caller is not allowed to do this (not the organiser)."""
    status_code = 403


def register_error_handlers(app: FastAPI) -> None:
    """Make every AppError return {"error": code, "message": text}."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message},
        )