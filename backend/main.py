"""FastAPI application entry point."""

import uvicorn
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.core.auth import require_auth
from backend.routers import (
    analysis,
    folders,
    jobs,
    ml_training,
    personas,
    playlist,
    polymarket,
    trading,
    transcripts,
    video,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for background services."""
    if settings.channel_monitoring_enabled:
        from backend.services.channel_monitor_service import start_monitor
        await start_monitor()
    yield
    from backend.services.channel_monitor_service import stop_monitor
    await stop_monitor()


app = FastAPI(
    title="Transcript Analysis API",
    description="Backend API for press briefing transcription and analysis",
    version="2.0.0",
    dependencies=[Depends(require_auth)],
    lifespan=lifespan,
)

# CORS middleware for Nuxt frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}


# Include all routers
app.include_router(jobs.router)
app.include_router(transcripts.router)
app.include_router(folders.router)
app.include_router(analysis.router)
app.include_router(video.router)
app.include_router(playlist.router)
app.include_router(polymarket.router)
app.include_router(personas.router)
app.include_router(ml_training.router)
app.include_router(trading.router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
