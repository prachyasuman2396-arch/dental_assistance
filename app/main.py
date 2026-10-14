import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import logger
from app.api.v1 import api_v1_router, health_router
from app.db.session import init_vector_extension


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    os.makedirs(settings.UPLOAD_STORAGE_DIR, exist_ok=True)
    await init_vector_extension()
    yield
    # Shutdown actions
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Production-oriented AI study and research assistant "
        "designed for students. Integrates LangGraph, dual-LLM "
        "routing (Groq + Gemini), pgvector document RAG, scholarly literature research, "
        "and active-recall study tools."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
origins = (
    [o.strip() for o in settings.CORS_ORIGINS]
    if isinstance(settings.CORS_ORIGINS, list)
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred while processing your request.",
            "error_type": exc.__class__.__name__,
        },
    )

# Register API Routers
app.include_router(health_router)
app.include_router(api_v1_router)


@app.get("/")
async def root():
    return {
        "message": f"Welcome to the {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "version": "0.1.0",
    }
