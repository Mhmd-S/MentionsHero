"""FastAPI application entry point."""

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.core.auth import require_auth
from backend.routers import (
    analysis,
    folders,
    jobs,
    kalshi,
    personas,
    playlist,
    public,
    transcripts,
    video,
)

settings = get_settings()

app = FastAPI(
    title="Transcript Analysis API",
    description="Backend API for press briefing transcription and analysis",
    version="2.0.0",
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


# Authenticated routers
auth_dep = [Depends(require_auth)]
app.include_router(jobs.router, dependencies=auth_dep)
app.include_router(transcripts.router, dependencies=auth_dep)
app.include_router(folders.router, dependencies=auth_dep)
app.include_router(analysis.router, dependencies=auth_dep)
app.include_router(video.router, dependencies=auth_dep)
app.include_router(playlist.router, dependencies=auth_dep)
app.include_router(kalshi.router, dependencies=auth_dep)
app.include_router(personas.router, dependencies=auth_dep)

# Public routers (no auth)
app.include_router(public.router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
