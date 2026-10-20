"""Health endpoints. Liveness never depends on the database."""
from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live():
    s = get_settings()
    return {"status": "alive", "app_env": s.app_env}


@router.get("/ready")
def ready():
    ok, detail = check_database()
    return {"status": "ready" if ok else "degraded", "database": detail}
