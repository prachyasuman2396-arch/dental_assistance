from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings
from app.llm.groq_client import GroqClient
from app.llm.gemini_client import GeminiClient

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "unknown",
        "pgvector_extension": "unknown",
        "providers": {
            "groq": "configured" if settings.GROQ_API_KEY else "unconfigured",
            "gemini": "configured" if (settings.ENABLE_GEMINI and settings.GEMINI_API_KEY) else "disabled_or_unconfigured",
        },
        "embedding": {
            "provider": settings.EMBEDDING_PROVIDER,
            "dimension": settings.EMBEDDING_DIMENSION,
        },
    }

    # 1. Database connection check
    try:
        res = await session.execute(text("SELECT 1;"))
        if res.scalar() == 1:
            health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"disconnected: {str(e)}"
        health_status["status"] = "degraded"

    # 2. pgvector check
    try:
        vec_res = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        )
        row = vec_res.scalar_one_or_none()
        health_status["pgvector_extension"] = "installed" if row else "missing"
    except Exception:
        health_status["pgvector_extension"] = "not_available"

    return health_status
