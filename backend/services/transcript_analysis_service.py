"""One-time transcript analysis service using Gemini."""

import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types

from backend.config import get_settings
from backend.core.database import get_supabase, set_cached_analysis
from backend.core.exceptions import CancellationError
from backend.models.job import JobStatus
from backend.services import job_service, transcript_service
from backend.services.transcription_service import with_retry

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are analyzing a transcript of a streamer who trades on Kalshi mention markets \
(prediction markets that resolve based on whether a person/term is mentioned during specific events \
like press briefings, speeches, or interviews).

Extract the following from this transcript. Be specific — include concrete examples, names, and numbers when available.

1. **Trading decisions**: Any buys, sells, holds, or position changes discussed, and the reasoning behind them.
2. **Entry/exit timing**: When and why they enter or exit positions (e.g., before an event, during live action, on dips).
3. **Risk management**: Position sizing, cutting losses, hedging, bankroll management.
4. **Mistakes and losses**: Any errors discussed, bad trades, or lessons learned from losses.
5. **Mental models**: Frameworks for thinking about mention markets — how they evaluate probability, read situations, etc.
6. **Key quotes**: Notable statements that capture trading wisdom or strategy.

If a category has no relevant content in this transcript, return an empty list for it.

Transcript title: {name}

Transcript:
{text}"""

SYNTHESIS_PROMPT = """You are creating a comprehensive trading strategy guide based on analysis of {count} \
transcripts from a Kalshi mention markets trader (prediction markets that resolve based on whether \
a person/term is mentioned during specific events).

Below are extracted insights from each trading session. Synthesize them into a well-structured, \
actionable guide in markdown. Be specific — reference concrete examples and patterns observed across sessions.

## Sections to include:

1. **Trading Style Overview** — How this trader approaches mention markets overall
2. **Entry & Exit Strategy Patterns** — When and how they enter/exit positions, what triggers action
3. **Risk Management Approach** — Position sizing, loss limits, bankroll management
4. **Tips & Tricks** — Specific actionable advice observed across sessions
5. **Common Mistakes to Avoid** — Errors they've discussed or demonstrated
6. **Mental Framework for Mention Markets** — How to think about probability, event dynamics, etc.
7. **Notable Quotes** — Best quotes that capture their trading philosophy

---

{insights}"""


# Structured schema for per-transcript extraction
_extraction_schema = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "trading_decisions": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="Trading decisions observed (buys, sells, holds) with reasoning"
        ),
        "entry_exit_timing": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="Entry/exit timing patterns and triggers"
        ),
        "risk_management": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="Risk management behaviors observed"
        ),
        "mistakes_and_losses": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="Mistakes discussed or losses taken, with lessons"
        ),
        "mental_models": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="Mental models and frameworks for mention markets"
        ),
        "key_quotes": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="Notable quotes capturing trading wisdom"
        ),
    },
    required=[
        "trading_decisions", "entry_exit_timing", "risk_management",
        "mistakes_and_losses", "mental_models", "key_quotes"
    ]
)


async def extract_transcript_insights(
    client: genai.Client,
    text: str,
    name: str
) -> dict[str, Any]:
    """Extract trading insights from a single transcript via Gemini."""
    # Truncate very long transcripts to stay within context limits (~200k tokens)
    max_chars = 800_000
    if len(text) > max_chars:
        logger.warning("Transcript '%s' truncated from %d to %d chars", name, len(text), max_chars)
        text = text[:max_chars]

    prompt = EXTRACTION_PROMPT.format(name=name, text=text)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_extraction_schema
    )

    async def generate():
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[types.Part.from_text(text=prompt)],
                config=config
            )
        )
        return response

    response = await with_retry(generate, service_name="Gemini Analysis")
    return json.loads(response.text)


async def synthesize_analysis(
    client: genai.Client,
    all_insights: list[dict[str, Any]],
    transcript_count: int
) -> str:
    """Synthesize per-transcript insights into a final markdown report."""
    # Format insights for the synthesis prompt
    parts = []
    for i, insights in enumerate(all_insights, 1):
        section = f"### Session {i}\n"
        for key, items in insights.items():
            if items:
                label = key.replace("_", " ").title()
                section += f"**{label}:**\n"
                for item in items:
                    section += f"- {item}\n"
        parts.append(section)

    combined = "\n---\n".join(parts)
    prompt = SYNTHESIS_PROMPT.format(count=transcript_count, insights=combined)

    async def generate():
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[types.Part.from_text(text=prompt)],
            )
        )
        return response

    response = await with_retry(generate, service_name="Gemini Synthesis")
    return response.text


REPORT_CACHE_PREFIX = "transcript_analysis:"


async def save_report(folder_id: str, report: str, transcript_count: int) -> None:
    """Save a completed analysis report to analysis_cache."""
    from datetime import datetime, timezone
    cache_key = f"{REPORT_CACHE_PREFIX}{folder_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    await set_cached_analysis(
        cache_key,
        {
            "folder_id": folder_id,
            "report": report,
            "transcript_count": transcript_count,
        },
        expires_hours=87600,  # ~10 years
    )


async def get_reports() -> list[dict[str, Any]]:
    """List all saved transcript analysis reports."""
    supabase = get_supabase()
    response = (
        supabase.table("analysis_cache")
        .select("id, cache_key, result, created_at")
        .like("cache_key", f"{REPORT_CACHE_PREFIX}%")
        .order("created_at", desc=True)
        .execute()
    )
    reports = []
    for row in response.data or []:
        result = row.get("result", {})
        reports.append({
            "id": row["id"],
            "folder_id": result.get("folder_id"),
            "transcript_count": result.get("transcript_count", 0),
            "created_at": row.get("created_at"),
        })
    return reports


async def get_report(report_id: str) -> dict[str, Any] | None:
    """Get a single saved report by its analysis_cache ID."""
    supabase = get_supabase()
    response = (
        supabase.table("analysis_cache")
        .select("id, cache_key, result, created_at")
        .eq("id", report_id)
        .like("cache_key", f"{REPORT_CACHE_PREFIX}%")
        .single()
        .execute()
    )
    if not response.data:
        return None
    row = response.data
    result = row.get("result", {})
    return {
        "id": row["id"],
        "folder_id": result.get("folder_id"),
        "transcript_count": result.get("transcript_count", 0),
        "report": result.get("report", ""),
        "created_at": row.get("created_at"),
    }


async def delete_report(report_id: str) -> bool:
    """Delete a saved report."""
    supabase = get_supabase()
    response = (
        supabase.table("analysis_cache")
        .delete()
        .eq("id", report_id)
        .like("cache_key", f"{REPORT_CACHE_PREFIX}%")
        .execute()
    )
    return bool(response.data)


async def run_transcript_analysis(job_id: str, folder_id: str) -> None:
    """Orchestrate the full map-reduce transcript analysis pipeline."""
    try:
        # Update status to transcribing (reuse existing status)
        await job_service.update_job_progress(
            job_id, JobStatus.TRANSCRIBING,
            stage_progress={"substep": "Loading transcripts", "substep_detail": "Fetching from folder..."}
        )

        # Fetch transcripts
        transcripts = await transcript_service.get_transcripts_in_folder_tree(folder_id)
        if not transcripts:
            await job_service.update_job_progress(
                job_id, JobStatus.FAILED,
                error_message="No transcripts found in folder"
            )
            return

        total = len(transcripts)
        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        # Map phase: extract insights from each transcript
        all_insights: list[dict[str, Any]] = []
        for i, t in enumerate(transcripts, 1):
            # Check cancellation
            if await job_service.check_cancellation(job_id):
                await job_service.mark_job_cancelled(job_id)
                return

            name = t.get("name", f"Transcript {i}")
            text = t.get("transcript", "")
            if not text:
                logger.info("Skipping empty transcript: %s", name)
                continue

            await job_service.update_job_progress(
                job_id, JobStatus.TRANSCRIBING,
                stage_progress={
                    "substep": "Analyzing transcripts",
                    "substep_detail": f"Processing: {name}",
                    "current_chunk": i,
                    "total_chunks": total
                }
            )

            insights = await extract_transcript_insights(client, text, name)
            all_insights.append(insights)

        if not all_insights:
            await job_service.update_job_progress(
                job_id, JobStatus.FAILED,
                error_message="No transcript content to analyze"
            )
            return

        # Reduce phase: synthesize final report
        await job_service.update_job_progress(
            job_id, JobStatus.SAVING,
            stage_progress={
                "substep": "Synthesizing report",
                "substep_detail": f"Combining insights from {len(all_insights)} transcripts..."
            }
        )

        report = await synthesize_analysis(client, all_insights, len(all_insights))

        # Persist report to analysis_cache (effectively permanent)
        await save_report(folder_id, report, total)

        # Complete with result in stage_progress
        await job_service.update_job_progress(
            job_id, JobStatus.COMPLETED,
            stage_progress={"result": report}
        )

    except CancellationError:
        await job_service.mark_job_cancelled(job_id)
    except Exception as e:
        logger.exception("Transcript analysis failed for job %s", job_id)
        await job_service.update_job_progress(
            job_id, JobStatus.FAILED,
            error_message=str(e)
        )
