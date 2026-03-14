"""Transcript filtering and highlighting utilities."""

import html
import re
from typing import Any


def parse_transcript(transcript: str) -> list[dict[str, Any]]:
    """Parse a transcript string into segments with speaker labels."""
    segments: list[dict[str, Any]] = []
    lines = transcript.split('\n')

    current_speaker: str | None = None
    current_timestamp: str | None = None
    current_content: list[str] = []

    # Match: Optional [MM:SS] timestamp, then name followed by colon
    # Supports: "[00:00] Gabe:", "Caroline:", "[12:34] SPEAKER_00:", "John Smith:"
    # Using broad pattern: [A-Z0-9] start, allowed chars, max 60 chars
    speaker_pattern = re.compile(
        r'^(?:\[(\d{1,3}:\d{2})\]\s+)?([A-Z0-9][\w\s\-\'._()]{1,60}?):\s*(.*)$'
    )

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        match = speaker_pattern.match(trimmed)
        if match:
            # Save previous segment if exists
            if current_speaker is not None and current_content:
                segment_data: dict[str, Any] = {
                    'speaker': current_speaker,
                    'content': ' '.join(current_content).strip()
                }
                if current_timestamp:
                    segment_data['timestamp'] = current_timestamp
                segments.append(segment_data)
            # Start new segment (group 1=timestamp, group 2=speaker, group 3=content)
            current_timestamp = match.group(1)  # may be None
            current_speaker = match.group(2)
            current_content = [match.group(3)] if match.group(3) else []
        elif current_speaker is not None:
            # Continue current segment
            current_content.append(trimmed)

    # Add last segment
    if current_speaker is not None and current_content:
        segment_data = {
            'speaker': current_speaker,
            'content': ' '.join(current_content).strip()
        }
        if current_timestamp:
            segment_data['timestamp'] = current_timestamp
        segments.append(segment_data)

    return segments


def escape_html(text: str) -> str:
    """Escape HTML to prevent XSS."""
    return html.escape(text)


def highlight_text(text: str, search_string: str) -> str:
    """Highlight matching text in a string (whole word match)."""
    if not search_string or not search_string.strip():
        return escape_html(text)

    pattern = re.compile(r'\b' + re.escape(search_string) + r'\b', re.IGNORECASE)
    parts: list[str] = []
    last_index = 0

    for match in pattern.finditer(text):
        # Add text before match
        if match.start() > last_index:
            parts.append(escape_html(text[last_index:match.start()]))
        # Add highlighted match
        parts.append(
            f'<mark class="bg-yellow-200 dark:bg-yellow-900">'
            f'{escape_html(match.group())}</mark>'
        )
        last_index = match.end()

    # If no matches found, return escaped text
    if not parts:
        return escape_html(text)

    # Add remaining text
    if last_index < len(text):
        parts.append(escape_html(text[last_index:]))

    return ''.join(parts)


def highlight_transcript(
    transcript: str,
    search_string: str | None = None,
) -> dict[str, Any]:
    """
    Highlight search term occurrences in transcript text.

    Returns dict with highlightedTranscript and matchCount (total word matches).
    """
    segments = parse_transcript(transcript)

    match_count = 0
    lines: list[str] = []
    current_speaker: str | None = None
    word_pattern = re.compile(r'\b' + re.escape(search_string) + r'\b', re.IGNORECASE) if search_string and search_string.strip() else None

    for segment in segments:
        # Count individual word matches (not just segments)
        if word_pattern:
            match_count += len(word_pattern.findall(segment['content']))

        # Add speaker label with optional timestamp
        if segment['speaker'] != current_speaker:
            if lines:
                lines.append('')
            timestamp = segment.get('timestamp')
            if timestamp:
                lines.append(f'[{escape_html(timestamp)}] {escape_html(segment["speaker"])}:')
            else:
                lines.append(f'{escape_html(segment["speaker"])}:')
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

    word_pattern = re.compile(r'\b' + re.escape(search_lower) + r'\b')

    for segment in segments:
        content_lower = segment['content'].lower()
        count = len(word_pattern.findall(content_lower))

        if count > 0:
            current = frequency_map.get(segment['speaker'], 0)
            frequency_map[segment['speaker']] = current + count

    # Convert to list and sort by count descending
    return sorted(
        [{'speaker': speaker, 'count': count} for speaker, count in frequency_map.items()],
        key=lambda x: x['count'],
        reverse=True
    )
