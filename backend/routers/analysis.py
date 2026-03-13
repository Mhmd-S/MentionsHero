"""Analysis API routes."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from backend.core.database import get_cached_analysis, set_cached_analysis
from backend.services import transcript_service, speaker_service, transcript_analysis_service
from backend.services import job_service
from backend.utils.nlp import (
    calculate_term_frequency,
    calculate_all_term_frequencies,
    extract_ngrams,
    search_term_in_context,
)
from backend.models.analysis import (
    TermFrequencyRequest,
    TermFrequencyResponse,
    AllTermsRequest,
    AllTermsResponse,
    NgramsRequest,
    NgramsResponse,
    SearchRequest,
    SearchResponse,
    SpeakersResponse,
    TranscriptAnalysisRequest,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/transcript-analysis")
async def run_transcript_analysis_endpoint(
    request: TranscriptAnalysisRequest,
    background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Launch a background LLM analysis of all transcripts in a folder."""
    job = await job_service.create_job(youtube_url=f"analysis:{request.folder_id}")
    background_tasks.add_task(
        transcript_analysis_service.run_transcript_analysis,
        job["id"],
        request.folder_id
    )
    return {"jobId": job["id"]}


@router.get("/transcript-analysis/reports")
async def list_reports() -> list[dict[str, Any]]:
    """List all saved transcript analysis reports."""
    return await transcript_analysis_service.get_reports()


@router.get("/transcript-analysis/reports/{report_id}")
async def get_report(report_id: str) -> dict[str, Any]:
    """Get a single saved report."""
    report = await transcript_analysis_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.delete("/transcript-analysis/reports/{report_id}")
async def delete_report(report_id: str) -> dict[str, str]:
    """Delete a saved report."""
    deleted = await transcript_analysis_service.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "deleted"}


async def _get_transcripts_for_folder(folder_id: str | None) -> list[dict[str, Any]]:
    """Get transcripts, optionally filtered by folder tree."""
    if folder_id:
        return await transcript_service.get_transcripts_in_folder_tree(folder_id)
    return await transcript_service.get_all_transcripts()


@router.get("/speakers")
async def list_speakers(
    folder_id: str | None = Query(None, alias="folder_id")
) -> SpeakersResponse:
    """
    List all speakers found across transcripts (from database).
    """
    speakers = await speaker_service.get_all_speakers(folder_id)
    return SpeakersResponse(speakers=speakers)


@router.get("/speakers/search")
async def search_speakers_endpoint(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200)
) -> SpeakersResponse:
    """Search speakers by name."""
    speakers = await speaker_service.search_speakers(q, limit)
    return SpeakersResponse(speakers=speakers)


@router.post("/speakers/migrate")
async def migrate_speakers(
    folder_id: str | None = Query(
        None,
        description="Optional: migrate only transcripts in this folder tree"
    )
) -> dict[str, int]:
    """
    One-time migration: extract and save speakers from existing transcripts.
    Safe to call multiple times (idempotent).
    """
    if folder_id:
        transcripts = await transcript_service.get_transcripts_in_folder_tree(folder_id)
    else:
        transcripts = await transcript_service.get_all_transcripts()

    migrated = 0
    skipped = 0
    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            skipped += 1
            continue
        await speaker_service.extract_and_save_transcript_speakers(
            t["id"], transcript_text
        )
        migrated += 1

    return {
        "migrated": migrated,
        "skipped": skipped,
        "total": len(transcripts)
    }


@router.get("/terms")
async def analyze_all_terms_get(
    min_frequency: int = Query(5, ge=1),
    max_terms: int = Query(500, ge=1, le=1000),
    folder_id: str | None = Query(None),
    speakers: str | None = Query(None)
) -> AllTermsResponse:
    """Get frequency of all terms above a threshold (GET version)."""
    speaker_list = None
    if speakers:
        speaker_list = [s.strip() for s in speakers.split(",") if s.strip()]

    speakers_key = ",".join(sorted(speaker_list)) if speaker_list else ""
    cache_key = f"all_terms:{folder_id}:{speakers_key}:{min_frequency}:{max_terms}"

    cached = await get_cached_analysis(cache_key)
    if cached:
        return AllTermsResponse(**cached)

    transcripts = await _get_transcripts_for_folder(folder_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found")

    result = calculate_all_term_frequencies(
        transcripts,
        min_frequency,
        max_terms,
        speakers=speaker_list
    )

    response_data = {
        "terms": result,
        "count": len(result),
        "folder_id": folder_id
    }

    # Cache for 1 hour
    await set_cached_analysis(cache_key, response_data, expires_hours=1)

    return AllTermsResponse(**response_data)


@router.post("/all-terms")
async def analyze_all_terms_post(request: AllTermsRequest) -> AllTermsResponse:
    """Get frequency of all terms above a threshold (POST version)."""
    speakers_key = ",".join(sorted(request.speakers)) if request.speakers else ""
    cache_key = f"all_terms:{request.folder_id}:{speakers_key}:{request.min_frequency}:{request.max_terms}"

    cached = await get_cached_analysis(cache_key)
    if cached:
        return AllTermsResponse(**cached)

    transcripts = await _get_transcripts_for_folder(request.folder_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found")

    result = calculate_all_term_frequencies(
        transcripts,
        request.min_frequency,
        request.max_terms,
        speakers=request.speakers
    )

    response_data = {
        "terms": result,
        "count": len(result),
        "folder_id": request.folder_id
    }

    # Cache for 1 hour
    await set_cached_analysis(cache_key, response_data, expires_hours=1)

    return AllTermsResponse(**response_data)


@router.get("/ngrams")
async def analyze_ngrams_get(
    n: int = Query(2, ge=2, le=3),
    min_frequency: int = Query(3, ge=1),
    max_ngrams: int = Query(200, ge=1, le=500),
    folder_id: str | None = Query(None),
    speakers: str | None = Query(None)
) -> NgramsResponse:
    """Extract n-gram phrases from transcripts (GET version)."""
    speaker_list = None
    if speakers:
        speaker_list = [s.strip() for s in speakers.split(",") if s.strip()]

    speakers_key = ",".join(sorted(speaker_list)) if speaker_list else ""
    cache_key = f"ngrams:{folder_id}:{speakers_key}:{n}:{min_frequency}:{max_ngrams}"

    cached = await get_cached_analysis(cache_key)
    if cached:
        return NgramsResponse(**cached)

    transcripts = await _get_transcripts_for_folder(folder_id)
    if not transcripts:
        raise HTTPException(status_code=404, detail="No transcripts found")

    result = extract_ngrams(
        transcripts,
        n,
        min_frequency,
        max_ngrams,
        speakers=speaker_list
    )

    response_data = {
        "ngrams": result,
        "n": n,
        "count": len(result),
        "folder_id": folder_id
    }

    # Cache for 1 hour
    await set_cached_analysis(cache_key, response_data, expires_hours=1)

    return NgramsResponse(**response_data)


@router.post("/ngrams")
async def analyze_ngrams_post(request: NgramsRequest) -> NgramsResponse:
    """Extract n-gram phrases from transcripts (POST version)."""
    speakers_key = ",".join(sorted(request.speakers)) if request.speakers else ""
    cache_key = f"ngrams:{request.folder_id}:{speakers_key}:{request.n}:{request.min_frequency}:{request.max_ngrams}"

    cached = await get_cached_analysis(cache_key)
    if cached:
        return NgramsResponse(**cached)

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

    response_data = {
        "ngrams": result,
        "n": request.n,
        "count": len(result),
        "folder_id": request.folder_id
    }

    # Cache for 1 hour
    await set_cached_analysis(cache_key, response_data, expires_hours=1)

    return NgramsResponse(**response_data)


@router.post("/search")
async def analyze_search(request: SearchRequest) -> SearchResponse:
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
    return SearchResponse(**result)


@router.get("/term/{term}")
async def get_term_frequency(
    term: str,
    case_sensitive: bool = Query(False, alias="case_sensitive"),
    folder_id: str | None = Query(None, alias="folder_id"),
    speakers: str | None = Query(None),
    persona_id: str | None = Query(None, alias="persona_id")
) -> TermFrequencyResponse:
    """Get frequency analysis for a specific term.

    If persona_id is provided, uses the persona's aliases as speakers filter
    and only searches transcripts containing the persona.
    """
    from backend.services import persona_service

    if not term.strip():
        raise HTTPException(status_code=400, detail="Term cannot be empty")

    speaker_list = None
    if speakers:
        speaker_list = [s.strip() for s in speakers.split(",") if s.strip()]

    # If persona_id is provided, use persona's aliases and transcripts
    if persona_id:
        persona = await persona_service.get_persona_by_id(persona_id)
        if persona:
            speaker_list = persona.get("aliases", [])
            # Get transcripts for this persona
            persona_transcripts = await persona_service.get_transcripts_for_persona(persona_id)
            if not persona_transcripts:
                return TermFrequencyResponse(
                    term=term,
                    total_mentions=0,
                    briefings_with_term=0,
                    total_briefings=0,
                    percentage=0.0,
                    trend="stable",
                    mentions_by_date=[]
                )
            transcript_ids = [t["id"] for t in persona_transcripts]
            transcripts = await transcript_service.get_transcripts_by_ids(transcript_ids)
        else:
            transcripts = await _get_transcripts_for_folder(folder_id)
    else:
        transcripts = await _get_transcripts_for_folder(folder_id)

    if not transcripts:
        return TermFrequencyResponse(
            term=term,
            total_mentions=0,
            briefings_with_term=0,
            total_briefings=0,
            percentage=0.0,
            trend="stable",
            mentions_by_date=[]
        )

    result = calculate_term_frequency(
        transcripts,
        term,
        case_sensitive,
        speakers=speaker_list
    )
    return TermFrequencyResponse(**result)


@router.post("/term-frequency")
async def analyze_term_frequency(request: TermFrequencyRequest) -> TermFrequencyResponse:
    """Get frequency analysis for a specific term (POST version)."""
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
    return TermFrequencyResponse(**result)
