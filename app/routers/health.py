from datetime import datetime
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import psutil

from app.db.session import get_db, engine
from app.core.config import get_settings

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)):
    """
    Basic health check endpoint.
    Returns the current status of the application.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check endpoint.
    Verifies that the application is ready to serve traffic.
    """
    checks = {
        "database": False,
        "memory": False,
    }
    
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    
    # Check memory usage (fail if > 90%)
    try:
        memory_percent = psutil.virtual_memory().percent
        checks["memory"] = memory_percent < 90
    except Exception:
        checks["memory"] = True  # Assume OK if we can't check
    
    all_healthy = all(checks.values())
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


@router.get("/health/live", status_code=status.HTTP_200_OK)
def liveness_check():
    """
    Liveness check endpoint.
    Kubernetes-style probe to check if the application is alive.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/db", status_code=status.HTTP_200_OK)
def database_health_check(db: Session = Depends(get_db)):
    """
    Database health check endpoint.
    Returns detailed database connection information.
    """
    try:
        # Get PostgreSQL version
        result = db.execute(text("SELECT version()"))
        db_version = result.scalar()
        
        # Get connection pool stats
        pool = engine.pool
        pool_stats = {
            "pool_size": pool.size() if hasattr(pool, 'size') else "N/A",
            "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else "N/A",
            "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else "N/A",
            "overflow": pool.overflow() if hasattr(pool, 'overflow') else "N/A",
        }
        
        return {
            "status": "healthy",
            "database": {
                "version": db_version,
                "pool_stats": pool_stats,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }

