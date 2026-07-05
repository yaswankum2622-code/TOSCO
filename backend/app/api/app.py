"""FastAPI app factory for the TOSCO demo backend."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import ApiRouteError, router
from app.api.schemas import ErrorResponse
from app.api.state import InMemoryApiState
from app.config import load_settings_from_env


logger = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    """Create the FastAPI app with shared demo state and route handlers."""

    app = FastAPI(title="TOSCO", version="0.1.0")
    app.state.tosco_state = InMemoryApiState()

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def log_startup_configuration() -> None:
        settings = load_settings_from_env()
        logger.info(
            "TOSCO startup: vultr_configured=%s base_url=%s model=%s fallback_enabled=%s",
            bool(settings.vultr_api_key),
            settings.vultr_inference_base_url,
            settings.vultr_chat_model,
            settings.tosco_fallback,
        )

    @app.exception_handler(ApiRouteError)
    async def handle_api_route_error(_: Request, exc: ApiRouteError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=exc.error_code,
                message=exc.message,
                error=exc.error,
                detail=exc.detail,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_code="INVALID_REQUEST",
                message="Request validation failed.",
                error="INVALID_REQUEST",
                detail="Request validation failed.",
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        del exc
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An unexpected backend error occurred.",
                error="INTERNAL_ERROR",
                detail="An unexpected backend error occurred.",
            ).model_dump(mode="json"),
        )

    app.include_router(router)
    return app


app = create_app()
