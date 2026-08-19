import structlog
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from rag_anything.db.session import get_sessionmaker

log = structlog.get_logger(__name__)

router= APIRouter(
    prefix='/health', 
    tags=['health']
)

@router.get('', status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """Reports whether the application is running."""
    return {"status": "ok"}

@router.get('/ready', status_code=status.HTTP_200_OK)
async def readiness(response: Response) -> dict[str, object]:
    """Reports whether the database is reachable."""
    checks: dict[str, str] = {}
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        log.warning("readiness.postgres_failed", error=str(exc))
        checks["postgres"] = "error"

    ready = all(v == "ok" for v in checks.values())
    response.status_code = (
        status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return {"status": "ready" if ready else "degraded", "checks": checks}