"""Transcript filtering and highlighting utilities."""

import html
import re
from typing import Any


def parse_transcript(transcript: str) -> list[dict[str, Any]]:
    """Parse a transcript string into segments with speaker labels."""
    segments: list[dict[str, Any]] = []
    lines = transcript.split('\n')

    current_speaker: str | None = None
    current_content: list[str] = []

    # Match: Name at start of line followed by colon
    # Supports: "Gabe:", "Caroline:", "SPEAKER_00:", "John Smith:", "PM (Keir Starmer):", "KIER_STARMER:"
    # Using broad pattern: [A-Z0-9] start, allowed chars, max 60 chars
    speaker_pattern = re.compile(
        r'^([A-Z0-9][\w\s\-\'._()]{1,60}?):\s*(.*)$'
    )

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        match = speaker_pattern.match(trimmed)
        if match:
            # Save previous segment if exists
            if current_speaker is not None and current_content:
                segments.append({
                    'speaker': current_speaker,
                    'content': ' '.join(current_content).strip()
                })
            # Start new segment
            current_speaker = match.group(1)
            current_content = [match.group(2)] if match.group(2) else []
        elif current_speaker is not None:
            # Continue current segment
            current_content.append(trimmed)

    # Add last segment
    if current_speaker is not None and current_content:
        segments.append({
            'speaker': current_speaker,
            'content': ' '.join(current_content).strip()
        })

    return segments


def escape_html(text: str) -> str:
    """Escape HTML to prevent XSS."""
    return html.escape(text)


def highlight_text(text: str, search_string: str) -> str:
    """Highlight matching text in a string."""
    if not search_string or not search_string.strip():
        return escape_html(text)

    search_lower = search_string.lower()
    text_lower = text.lower()
    parts: list[str] = []
    last_index = 0
    index = text_lower.find(search_lower, last_index)

    # If no matches found, return escaped text
    if index == -1:
        return escape_html(text)

    while index != -1:
        # Add text before match
        if index > last_index:
            parts.append(escape_html(text[last_index:index]))
        # Add highlighted match
        parts.append(
            f'<mark class="bg-yellow-200 dark:bg-yellow-900">'
            f'{escape_html(text[index:index + len(search_string)])}</mark>'
        )
        last_index = index + len(search_string)
        index = text_lower.find(search_lower, last_index)

    # Add remaining text
    if last_index < len(text):
        parts.append(escape_html(text[last_index:]))

    return ''.join(parts)


def highlight_transcript(
    transcript: str,
    search_string: str | None = None,
    speakers: list[str] | None = None
) -> dict[str, Any]:
    """
    Highlight transcript with search string and/or speaker highlighting.

    Returns dict with highlightedTranscript and matchCount.
    """
    segments = parse_transcript(transcript)

    match_count = 0
    lines: list[str] = []
    current_speaker: str | None = None

    for segment in segments:
        is_speaker_match = (
            speakers and
            len(speakers) > 0 and
            any(
                segment['speaker'] == speaker or
                segment['speaker'].lower() == speaker.lower() or
                speaker.lower() in segment['speaker'].lower()
                for speaker in speakers
            )
        )

        is_content_match = (
            search_string and
            search_string.strip() and
            search_string.lower() in segment['content'].lower()
        )

        is_match = is_speaker_match or is_content_match

        if is_match:
            match_count += 1

        # Add speaker label
        if segment['speaker'] != current_speaker:
            if lines:
                lines.append('')
            if is_speaker_match and speakers:
                speaker_label = (
                    f'<mark class="bg-blue-200 dark:bg-blue-900 font-semibold">'
                    f'{escape_html(segment["speaker"])}:</mark>'
                )
            else:
                speaker_label = f'{escape_html(segment["speaker"])}:'
            lines.append(speaker_label)
            current_speaker = segment['speaker']

        # Add content with highlighting
        if search_string and search_string.strip():
            highlighted_content = highlight_text(segment['content'], search_string)
        else:
            highlighted_content = escape_html(segment['content'])

        lines.append(highlighted_content)

    return {
        'highlightedTranscript': '\n'.join(lines),
        'matchCount': match_count
    }


def extract_speakers(transcript: str) -> list[str]:
    """Extract unique speakers from a transcript."""
    segments = parse_transcript(transcript)
    speakers = set()

    for segment in segments:
        speakers.add(segment['speaker'])

    return sorted(speakers)


def calculate_speaker_frequencies(
    transcript: str,
    search_string: str
) -> list[dict[str, Any]]:
    """Calculate search term frequency per speaker."""
    if not search_string or not search_string.strip():
        return []

    segments = parse_transcript(transcript)
    frequency_map: dict[str, int] = {}
    search_lower = search_string.lower()

    for segment in segments:
        content_lower = segment['content'].lower()
        count = 0
        index = content_lower.find(search_lower)

        while index != -1:
            count += 1
            index = content_lower.find(search_lower, index + 1)

        if count > 0:
            current = frequency_map.get(segment['speaker'], 0)
            frequency_map[segment['speaker']] = current + count

    # Convert to list and sort by count descending
    return sorted(
        [{'speaker': speaker, 'count': count} for speaker, count in frequency_map.items()],
        key=lambda x: x['count'],
        reverse=True
    )
