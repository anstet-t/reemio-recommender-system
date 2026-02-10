"""FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from recommendation_service.api.v1.router import api_router
from recommendation_service.config import get_settings
from recommendation_service.infrastructure.redis import close_redis
from recommendation_service.middleware.timing import TimingMiddleware

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if get_settings().debug else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(get_settings().log_level),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "Starting Reemio Recommender Service",
        app_env=settings.app_env,
        debug=settings.debug,
    )

    # Pre-warm the embedding model so first search isn't slow
    from recommendation_service.services.embedding import get_embedding_model
    logger.info("Pre-warming embedding model...")
    get_embedding_model()
    logger.info("Embedding model ready")

    yield

    await close_redis()
    logger.info("Shutting down Reemio Recommender Service")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Reemio Recommender API",
        description="E-commerce recommendation system providing personalized product recommendations",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(TimingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

        @app.get("/")
        async def serve_frontend():
            return FileResponse(FRONTEND_DIR / "index.html")

        @app.get("/app")
        async def serve_app():
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()


def run() -> None:
    """Run the application using uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "recommendation_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.api_workers,
    )


if __name__ == "__main__":
    run()
