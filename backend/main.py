"""FastAPI application entry point."""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.logging_config import setup_logging

setup_logging()
from backend.core.auth import require_admin
from backend.routers import (
    analysis,
    auto_transcription,
    channel,
    folders,
    jobs,
    kalshi,
    personas,
    playlist,
    polymarket,
    profile,
    public,
    transcripts,
    video,
)
from backend.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background scheduler."""
    await start_scheduler()
    yield
    await stop_scheduler()


app = FastAPI(
    title="Transcript Analysis API",
    description="Backend API for press briefing transcription and analysis",
    version="2.0.0",
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


# Admin routers (require admin role)
app.include_router(jobs.router, dependencies=[Depends(require_admin)])
app.include_router(transcripts.router, dependencies=[Depends(require_admin)])
app.include_router(folders.router, dependencies=[Depends(require_admin)])
app.include_router(analysis.router, dependencies=[Depends(require_admin)])
app.include_router(video.router, dependencies=[Depends(require_admin)])
app.include_router(playlist.router, dependencies=[Depends(require_admin)])
app.include_router(channel.router, dependencies=[Depends(require_admin)])
app.include_router(kalshi.router, dependencies=[Depends(require_admin)])
app.include_router(polymarket.router, dependencies=[Depends(require_admin)])
app.include_router(personas.router, dependencies=[Depends(require_admin)])
app.include_router(auto_transcription.router, dependencies=[Depends(require_admin)])

# Public router — fully anonymous, no auth of any kind.
app.include_router(public.router)
# Profile router — user-level auth. Its only consumer is the admin UI, which
# reads `profiles.role` from it to decide whether to render the admin shell.
app.include_router(profile.router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
