"""FastAPI application factory. `uvicorn app.main:app` serves the default instance."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.middleware import (
    BodySizeLimitMiddleware,
    MetricsMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.api.routes import router
from app.config import Settings, get_settings
from app.db import make_engine, make_sessionmaker
from app.errors import DomainError
from app.observability import QUEUE_AGE, QUEUE_DEPTH, setup_logging, setup_tracing
from app.repositories import Repo

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.engine.dispose()

    app = FastAPI(
        title="EvalOps API",
        version="1.0.0",
        lifespan=lifespan,
        separate_input_output_schemas=False,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    engine = make_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)

    if settings.environment != "test":
        setup_logging(settings)
    if setup_tracing(settings, settings.otel_service_name):
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,metrics")

    # Multipart overhead on top of the largest allowed upload.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_upload_bytes + 64 * 1024)
    app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        async with app.state.sessionmaker() as s:
            await s.execute(text("SELECT 1"))
        return {"status": "ok", "llm_provider": settings.llm_provider}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        # Queue gauges are computed here too, not only in the worker: if the worker dies,
        # its metrics vanish, and "queue stuck" must still be observable.
        async with app.state.sessionmaker() as s:
            repo = Repo(s)
            QUEUE_AGE.set(await repo.oldest_queued_age_seconds())
            QUEUE_DEPTH.set((await repo.count_runs_by_status()).get("queued", 0))
        return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(router, prefix=API_PREFIX)
    return app


app: FastAPI


def __getattr__(name: str) -> FastAPI:
    # Lazy default instance so importing this module (e.g. in tests) has no side effects.
    if name == "app":
        global app
        app = create_app()
        return app
    raise AttributeError(name)
