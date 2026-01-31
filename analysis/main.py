"""FastAPI server for transcript analysis."""

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db import get_all_transcripts, get_all_transcripts_in_folder_tree, get_folders, get_cached_analysis, set_cached_analysis, update_transcript_speakers
from nlp import (
    calculate_term_frequency,
    calculate_all_term_frequencies,
    extract_ngrams,
    search_term_in_context,
    extract_all_speakers,
    parse_transcript_segments,
)

app = FastAPI(
    title="Transcript Analysis API",
    description="NLP analysis service for press briefing transcripts",
    version="1.0.0"
)

# CORS middleware for Nuxt frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class TermFrequencyRequest(BaseModel):
    term: str
    case_sensitive: bool = False
    folder_id: str | None = None
    speakers: list[str] | None = None


class TermFrequencyResponse(BaseModel):
    term: str
    total_mentions: int
    briefings_with_term: int
    total_briefings: int
    percentage: float
    trend: str
    mentions_by_date: list[dict[str, Any]]


class AllTermsRequest(BaseModel):
    min_frequency: int = Field(default=5, ge=1)
    max_terms: int = Field(default=500, ge=1, le=1000)
    folder_id: str | None = None
    speakers: list[str] | None = None


class NgramsRequest(BaseModel):
    n: int = Field(default=2, ge=2, le=3)
    min_frequency: int = Field(default=3, ge=1)
    max_ngrams: int = Field(default=200, ge=1, le=500)
    folder_id: str | None = None
    speakers: list[str] | None = None


class SearchRequest(BaseModel):
    query: str
    context_chars: int = Field(default=200, ge=50, le=500)
    folder_id: str | None = None
    speakers: list[str] | None = None


async def _get_transcripts_for_folder(folder_id: str | None) -> list[dict[str, Any]]:
    if folder_id:
        return await get_all_transcripts_in_folder_tree(folder_id)
    return await get_all_transcripts(None)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Folders endpoint
@app.get("/folders")
async def list_folders():
    """List all folders."""
    folders = await get_folders()
    return {"folders": folders}


# Speakers endpoint (GET for UI dropdown)
@app.get("/analyze/speakers")
async def list_speakers(folder_id: str | None = None):
    """List all speakers found across transcripts. Extracts and saves speakers per transcript if not already stored."""
    if folder_id:
        transcripts = await get_all_transcripts_in_folder_tree(folder_id)
    else:
        transcripts = await get_all_transcripts(None)
    if not transcripts:
        return {"speakers": []}
    # Ensure speakers are extracted and saved for each transcript that is missing them
    for t in transcripts:
        stored = t.get("speakers")
        if stored is None or (isinstance(stored, list) and len(stored) == 0):
            transcript_text = t.get("transcript", "")
            if transcript_text:
                segments = parse_transcript_segments(transcript_text)
                names = sorted({s["speaker"] for s in segments})
                if names:
                    await update_transcript_speakers(t["id"], names)
    speakers = extract_all_speakers(transcripts)
    return {"speakers": speakers}


# Analysis endpoints
@app.post("/analyze/term-frequency", response_model=TermFrequencyResponse)
async def analyze_term_frequency(request: TermFrequencyRequest):
    """Get frequency analysis for a specific term."""
    if not request.term.strip():
        raise HTTPException(status_code=400, detail="Term cannot be empty")

    transcripts = await _get_transcripts_for_folder(request.folder_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found")

    result = calculate_term_frequency(
        transcripts,
        request.term,
        request.case_sensitive,
        speakers=request.speakers
    )
    return result


@app.post("/analyze/all-terms")
async def analyze_all_terms(request: AllTermsRequest):
    """Get frequency of all terms above a threshold."""
    speakers_key = ",".join(sorted(request.speakers)) if request.speakers else ""
    cache_key = f"all_terms:{request.folder_id}:{speakers_key}:{request.min_frequency}:{request.max_terms}"
    cached = await get_cached_analysis(cache_key)
    if cached:
        return cached

    transcripts = await _get_transcripts_for_folder(request.folder_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found")

    result = calculate_all_term_frequencies(
        transcripts,
        request.min_frequency,
        request.max_terms,
        speakers=request.speakers
    )

    response = {"terms": result, "count": len(result), "folder_id": request.folder_id}

    # Cache for 1 hour
    await set_cached_analysis(cache_key, response, expires_hours=1)

    return response


@app.post("/analyze/ngrams")
async def analyze_ngrams(request: NgramsRequest):
    """Extract n-gram phrases from transcripts."""
    speakers_key = ",".join(sorted(request.speakers)) if request.speakers else ""
    cache_key = f"ngrams:{request.folder_id}:{speakers_key}:{request.n}:{request.min_frequency}:{request.max_ngrams}"
    cached = await get_cached_analysis(cache_key)
    if cached:
        return cached

    transcripts = await _get_transcripts_for_folder(request.folder_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found")

    result = extract_ngrams(
        transcripts,
        request.n,
        request.min_frequency,
        request.max_ngrams,
        speakers=request.speakers
    )

    response = {"ngrams": result, "n": request.n, "count": len(result), "folder_id": request.folder_id}

    # Cache for 1 hour
    await set_cached_analysis(cache_key, response, expires_hours=1)

    return response


@app.post("/analyze/search")
async def analyze_search(request: SearchRequest):
    """Search for a term with context."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    transcripts = await _get_transcripts_for_folder(request.folder_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found")

    result = search_term_in_context(
        transcripts,
        request.query,
        request.context_chars,
        speakers=request.speakers
    )
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
