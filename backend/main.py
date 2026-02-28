"""FastAPI application entry point."""

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.core.auth import require_admin
from backend.routers import (
    analysis,
    folders,
    jobs,
    kalshi,
    personas,
    playlist,
    public,
    stripe_router,
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


# Admin routers (require admin role)
app.include_router(jobs.router, dependencies=[Depends(require_admin)])
app.include_router(transcripts.router, dependencies=[Depends(require_admin)])
app.include_router(folders.router, dependencies=[Depends(require_admin)])
app.include_router(analysis.router, dependencies=[Depends(require_admin)])
app.include_router(video.router, dependencies=[Depends(require_admin)])
app.include_router(playlist.router, dependencies=[Depends(require_admin)])
app.include_router(kalshi.router, dependencies=[Depends(require_admin)])
app.include_router(personas.router, dependencies=[Depends(require_admin)])

# Public routers (no global auth — per-endpoint auth where needed)
app.include_router(public.router)
app.include_router(stripe_router.router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
