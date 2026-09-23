"""FastAPI application factory.

Run with: uvicorn app.main:create_app --factory
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.middleware import RequestContextMiddleware
from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimiter
from app.db.session import dispose_engine
from app.services.pipeline import JobRunner
from app.services.store import Store

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "application_startup", extra={"environment": settings.environment, "version": __version__}
    )
    yield
    await app.state.runner.close()
    await dispose_engine()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="RepoMentor API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    register_exception_handlers(app)
    app.state.store = Store()
    app.state.runner = JobRunner(app.state.store, settings)
    app.state.limiter = RateLimiter()
    app.state.ask_semaphore = asyncio.Semaphore(2)

    # Middleware added last is outermost: CORS wraps request-context handling.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    app.include_router(health_router)
    app.include_router(api_v1_router)
    return app
