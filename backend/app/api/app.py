"""FastAPI app factory for the TOSCO demo backend."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import ApiRouteError, router
from app.api.schemas import ErrorResponse
from app.api.state import InMemoryApiState


def create_app() -> FastAPI:
    """Create the FastAPI app with shared demo state and route handlers."""

    app = FastAPI(title="TOSCO", version="0.1.0")
    app.state.tosco_state = InMemoryApiState()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiRouteError)
    async def handle_api_route_error(_: Request, exc: ApiRouteError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=exc.error, detail=exc.detail).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
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
                error="INTERNAL_ERROR",
                detail="An unexpected backend error occurred.",
            ).model_dump(mode="json"),
        )

    app.include_router(router)
    return app


app = create_app()
