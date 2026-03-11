from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time

from app.core.config import get_settings
from app.core.logging_config import setup_logging, get_logger
from app.core.exceptions import register_exception_handlers
from app.db.session import init_db, close_db
from app.routers import auth, sops, logs, analyze, dashboard, reports, health

settings = get_settings()
logger = get_logger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request timing headers."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    setup_logging()
    logger.info(
        "Application starting up",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )
    init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Application shutting down")
    close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready Pharma SOP Compliance Analyzer API",
    docs_url="/docs" if settings.DEBUG else "/docs",
    redoc_url="/redoc" if settings.DEBUG else "/redoc",
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Register exception handlers
register_exception_handlers(app)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.is_production:
    app.add_middleware(TimingMiddleware)

# Add Prometheus metrics
if settings.ENABLE_METRICS:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["monitoring"])

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(sops.router)
app.include_router(logs.router)
app.include_router(analyze.router)
app.include_router(dashboard.router)
app.include_router(reports.router)


@app.get(
    "/",
    tags=["root"],
    summary="Root endpoint",
    description="Get API information and status",
)
def root():
    """Root endpoint returning API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health",
        "metrics": "/metrics" if settings.ENABLE_METRICS else None,
    }


@app.get(
    "/info",
    tags=["root"],
    summary="API information",
    description="Get detailed API information",
)
def api_info():
    """Get detailed API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "debug": settings.DEBUG,
        "docs_url": "/docs" if settings.DEBUG else None,
        "openapi_url": "/openapi.json" if settings.DEBUG else None,
    }
