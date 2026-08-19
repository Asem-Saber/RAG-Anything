from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from rag_anything.api.middleware import RequestIdMiddleware
from rag_anything.api.router import api_router
from rag_anything.observability.logging import configure_logging
from rag_anything.settings import Settings, get_settings

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    log.info("api.startup", environment=settings.environment)
    yield
    log.info("api.shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_logs=not settings.is_dev)

    app = FastAPI(
        title="RAG-Anything",
        version="0.1.0",
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()