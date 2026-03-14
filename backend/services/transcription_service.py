"""Transcription service using Gemini API."""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Awaitable

from google import genai
from google.genai import types

from backend.config import get_settings
from backend.core.exceptions import CancellationError, TranscriptionError

logger = logging.getLogger(__name__)


async def with_retry(
    fn,
    max_retries: int = 3,
    base_delay: float = 1.0,
    service_name: str = "API"
):
    """Retry a function with exponential backoff."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            error_message = str(e)

            # Check if error is retryable
            is_retryable = (
                "502" in error_message or
                "503" in error_message or
                "504" in error_message or
                "429" in error_message or
                "Bad Gateway" in error_message or
                "rate limit" in error_message.lower()
            )

            if not is_retryable or attempt == max_retries:
                raise

            delay = base_delay * (2 ** attempt)
            logger.warning("%s error (attempt %d/%d), retrying in %ss: %s", service_name, attempt + 1, max_retries + 1, delay, e)
            await asyncio.sleep(delay)

    raise last_error


def format_gemini_transcript(segments: list[dict[str, str]]) -> str:
    """Format Gemini transcript segments into readable text."""
    lines: list[str] = []
    current_speaker = ""

    for segment in segments:
        if segment.get("speaker") != current_speaker:
            current_speaker = segment.get("speaker", "")
            # Add newline before speaker label (except for first speaker)
            if lines:
                lines.append("")
            lines.append(f"{current_speaker}:")
        # Add content on a new line after speaker label
        lines.append(segment.get("content", "").strip())

    return "\n".join(lines).strip()


async def upload_audio_to_gemini(
    client: genai.Client,
    audio_path: str,
    cancel_event: asyncio.Event | None = None
) -> dict[str, str]:
    """
    Upload audio file to Gemini.

    For files > 20MB, uses the Files API. Otherwise, returns marker for inline usage.
    """
    if cancel_event and cancel_event.is_set():
        raise CancellationError()

    file_size = os.path.getsize(audio_path)

    # Use Files API for files > 20MB
    if file_size > 20 * 1024 * 1024:
        async def upload():
            # Run synchronous upload in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.files.upload(file=audio_path)
            )
            return {"uri": result.uri, "mimeType": result.mime_type}

        return await with_retry(upload, service_name="Gemini Files API")
    else:
        # For smaller files, use inline data
        return {"uri": "inline", "mimeType": "audio/mp3"}


# Max length for user-provided speaker hint to avoid prompt bloat
SPEAKER_HINT_MAX_LENGTH = 500


ProgressCallback = Callable[[str], Awaitable[None]]


async def transcribe_with_gemini(
    client: genai.Client,
    audio_path: str,
    cancel_event: asyncio.Event | None = None,
    speaker_hint: str | None = None,
    video_title: str | None = None,
    progress_callback: ProgressCallback | None = None
) -> str:
    """Transcribe audio using Gemini with speaker diarization."""
    if cancel_event and cancel_event.is_set():
        raise CancellationError()

    prompt = """Process the audio file and generate a detailed transcription with speaker diarization.

Requirements:
1. Identify distinct speakers (e.g., Speaker 1, Speaker 2 format if names are not available).
2. Transcribe the speech accurately, preserving the natural flow of conversation.
3. Group consecutive segments from the same speaker together."""

    if video_title:
        prompt += f"""

Video title: {video_title}
Use this title as context to better understand the topic, identify speakers, and accurately transcribe domain-specific terms."""

    if speaker_hint:
        hint = speaker_hint.strip()[:SPEAKER_HINT_MAX_LENGTH]
        if hint:
            prompt += f"""

User-provided context for speaker identification:
{hint}
Use this context to label speakers with descriptive names where possible (e.g. PM, Opposition Leader, Caroline) instead of generic labels."""

    if progress_callback:
        await progress_callback("Uploading audio to Gemini...")

    file_info = await upload_audio_to_gemini(client, audio_path, cancel_event)

    # Build content parts
    if file_info["uri"] == "inline":
        # Use inline data for smaller files
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        contents = [
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3")
        ]
    else:
        # Use uploaded file URI
        contents = [
            types.Part.from_uri(file_uri=file_info["uri"], mime_type=file_info["mimeType"]),
            types.Part.from_text(text=prompt)
        ]

    # Define response schema
    response_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "segments": types.Schema(
                type=types.Type.ARRAY,
                description="List of transcribed segments with speaker and timestamp.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "speaker": types.Schema(
                            type=types.Type.STRING,
                            description="Speaker identifier (e.g., SPEAKER_00, SPEAKER_01, or name if available)"
                        ),
                        "timestamp": types.Schema(
                            type=types.Type.STRING,
                            description="Timestamp in MM:SS format"
                        ),
                        "content": types.Schema(
                            type=types.Type.STRING,
                            description="Transcribed text content"
                        )
                    },
                    required=["speaker", "timestamp", "content"]
                )
            )
        },
        required=["segments"]
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=response_schema
    )

    async def generate():
        # Run synchronous generation in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=contents,
                config=config
            )
        )
        return response

    if progress_callback:
        await progress_callback("Waiting for Gemini transcription...")

    response = await with_retry(generate, service_name="Gemini API")

    if cancel_event and cancel_event.is_set():
        raise CancellationError()

    if progress_callback:
        await progress_callback("Processing transcript...")

    response_text = response.text
    if not response_text:
        raise TranscriptionError("Gemini API returned empty response")

    try:
        parsed_response = json.loads(response_text)
    except json.JSONDecodeError:
        raise TranscriptionError("Failed to parse Gemini response")

    segments = parsed_response.get("segments", [])
    if not segments:
        raise TranscriptionError("Gemini API returned no transcription segments")

    return format_gemini_transcript(segments)


async def transcribe_audio(
    audio_path: str,
    cancel_event: asyncio.Event | None = None,
    speaker_hint: str | None = None,
    video_title: str | None = None,
    progress_callback: ProgressCallback | None = None
) -> str:
    """
    Transcribe audio file using Gemini.

    Main entry point for transcription service.
    """
    if cancel_event and cancel_event.is_set():
        raise CancellationError()

    settings = get_settings()

    if not settings.gemini_api_key:
        raise TranscriptionError("Gemini API key is not configured")

    client = genai.Client(api_key=settings.gemini_api_key)

    logger.info("Starting transcription for %s", audio_path)
    result = await transcribe_with_gemini(
        client, audio_path, cancel_event, speaker_hint=speaker_hint,
        video_title=video_title, progress_callback=progress_callback
    )
    logger.info("Transcription complete for %s", audio_path)
    return result
