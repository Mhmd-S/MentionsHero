"""NLP processing functions for transcript speaker extraction."""

import re
from typing import Any


def parse_transcript_segments(transcript: str) -> list[dict[str, Any]]:
    """Parse transcript into speaker segments.

    Matches speaker labels like "Caroline:", "SPEAKER_00:", "John Smith:" at start of lines.
    """
    segments: list[dict[str, Any]] = []
    lines = transcript.split('\n')

    speaker_pattern = re.compile(
        r'^(?:\[(\d{1,3}:\d{2})\]\s+)?([A-Z0-9][\w\s\-\'._()]{1,60}?):\s*(.*)$'
    )

    current_speaker: str | None = None
    current_content: list[str] = []

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        match = speaker_pattern.match(trimmed)
        if match:
            if current_speaker is not None and current_content:
                segments.append({
                    'speaker': current_speaker,
                    'content': ' '.join(current_content).strip()
                })
            current_speaker = match.group(2)
            current_content = [match.group(3)] if match.group(3) else []
        elif current_speaker is not None:
            current_content.append(trimmed)

    if current_speaker is not None and current_content:
        segments.append({
            'speaker': current_speaker,
            'content': ' '.join(current_content).strip()
        })

    return segments
