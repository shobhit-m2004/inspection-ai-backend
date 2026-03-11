from fastapi import Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> None:
    """Handle rate limit exceeded events."""
    logger.warning(
        "Rate limit exceeded",
        client_ip=request.client.host if request.client else "unknown",
        path=str(request.url.path),
        limit=exc.detail,
    )


def create_rate_limit_exceeded_handler():
    """Create rate limit exceeded handler."""
    return _rate_limit_exceeded_handler
