from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.study import router as study_router
from app.api.v1.health import router as health_router
from app.api.v1.profile import router as profile_router
from app.api.v1.memories import router as memories_router
from app.api.v1.mcp import router as mcp_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(conversations_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(study_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(memories_router)
api_v1_router.include_router(mcp_router)

__all__ = ["api_v1_router", "health_router"]

