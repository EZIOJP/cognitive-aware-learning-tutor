"""Unified API error envelope for clients and observability."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorBody(code=code, message=message, details=details)
        ).model_dump(),
    )


def register_exception_handlers(app) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return error_response(
                exc.status_code,
                code=str(detail["code"]),
                message=str(detail.get("message", detail)),
                details=detail.get("details"),
            )
        if isinstance(detail, list):
            return error_response(
                exc.status_code,
                code="http_error",
                message="Request failed",
                details=detail,
            )
        return error_response(
            exc.status_code,
            code="http_error",
            message=str(detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return error_response(
            422,
            code="validation_error",
            message="Request validation failed",
            details=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        from backend.config import get_settings

        settings = get_settings()
        message = str(exc) if settings.dev_mode else "Internal server error"
        return error_response(500, code="internal_error", message=message)
