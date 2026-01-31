"""NLP processing functions for transcript analysis."""

import re
from collections import Counter
from typing import Any

import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.util import ngrams as nltk_ngrams

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)

try:
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('averaged_perceptron_tagger', quiet=True)

try:
    nltk.data.find('taggers/averaged_perceptron_tagger_eng')
except LookupError:
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)

def clean_text(text: str) -> str:
    """Clean transcript text for analysis.

    Handles transcript format like:
        Caroline:
        Look, it's true that...

        Reporter:
        Thank you, Caroline...
    """
    # Remove speaker labels at the start of lines (e.g., "Caroline:", "Reporter:", "Reagan:")
    # Pattern matches: start of line, optional whitespace, name (letters only), colon, optional whitespace/newline
    text = re.sub(r'^\s*[A-Za-z]+:\s*\n?', '', text, flags=re.MULTILINE)
    # Also handle speaker labels like "SPEAKER_01:" from diarization
    text = re.sub(r'^\s*SPEAKER_\d+:\s*\n?', '', text, flags=re.MULTILINE)
    # Remove timestamps if present
    text = re.sub(r'\[\d{1,2}:\d{2}(:\d{2})?\]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_transcript_segments(transcript: str) -> list[dict[str, Any]]:
    """Parse transcript into speaker segments.

    Matches speaker labels like "Caroline:", "SPEAKER_00:", "John Smith:" at start of lines.
    """
    segments: list[dict[str, Any]] = []
    lines = transcript.split('\n')

    # Pattern: speaker name (letters, hyphens, underscores, or SPEAKER_N) followed by colon
    speaker_pattern = re.compile(
        r'^([A-Z][a-zA-Z\'-]*(?:\s+[A-Z][a-zA-Z\'-]*)?|SPEAKER_\d+):\s*(.*)$'
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
            current_speaker = match.group(1)
            current_content = [match.group(2)] if match.group(2) else []
        elif current_speaker is not None:
            current_content.append(trimmed)

    if current_speaker is not None and current_content:
        segments.append({
            'speaker': current_speaker,
            'content': ' '.join(current_content).strip()
        })

    return segments


def filter_by_speakers(transcript: str, speakers: list[str] | None) -> str:
    """Filter transcript to only include specified speakers' content.

    If speakers is None or empty, returns transcript unchanged (no filtering).
    Speaker matching is case-insensitive and supports partial match (e.g. "Karoline" matches "Karoline Leavitt").
    """
    if not speakers:
        return transcript

    segments = parse_transcript_segments(transcript)
    speaker_lower = [s.lower() for s in speakers]

    def speaker_matches(segment_speaker: str) -> bool:
        seg_lower = segment_speaker.lower()
        return any(
            seg_lower == sl or seg_lower.startswith(sl) or sl in seg_lower
            for sl in speaker_lower
        )

    filtered = [s for s in segments if speaker_matches(s['speaker'])]
    return ' '.join(s['content'] for s in filtered if s['content']).strip()


def extract_all_speakers(transcripts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract unique speakers from all transcripts with segment and briefing counts."""
    speaker_segment_count: dict[str, int] = {}
    speaker_briefings: dict[str, set[str]] = {}

    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            continue
        transcript_id = t.get("id") or t.get("name", "")
        segments = parse_transcript_segments(transcript_text)
        seen_speakers_this_briefing: set[str] = set()
        for s in segments:
            name = s['speaker']
            speaker_segment_count[name] = speaker_segment_count.get(name, 0) + 1
            seen_speakers_this_briefing.add(name)
        for name in seen_speakers_this_briefing:
            if name not in speaker_briefings:
                speaker_briefings[name] = set()
            speaker_briefings[name].add(str(transcript_id))

    result = []
    for name in sorted(speaker_segment_count.keys()):
        result.append({
            "name": name,
            "segment_count": speaker_segment_count[name],
            "briefings": len(speaker_briefings.get(name, set()))
        })
    return result


def calculate_term_frequency(
    transcripts: list[dict[str, Any]],
    term: str,
    case_sensitive: bool = False,
    speakers: list[str] | None = None
) -> dict[str, Any]:
    """Calculate frequency of a specific term across transcripts (optionally for specific speakers only)."""
    total_mentions = 0
    briefings_with_term = 0
    mentions_by_date: list[dict[str, Any]] = []

    search_term = term if case_sensitive else term.lower()

    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            continue

        # Filter to speaker(s) first if requested
        text_to_analyze = filter_by_speakers(transcript_text, speakers) if speakers else transcript_text
        cleaned_text = clean_text(text_to_analyze)
        text_to_search = cleaned_text if case_sensitive else cleaned_text.lower()

        # Count occurrences
        count = len(re.findall(re.escape(search_term), text_to_search))

        if count > 0:
            briefings_with_term += 1
            total_mentions += count
            mentions_by_date.append({
                "date": t.get("created_at", "")[:10] if t.get("created_at") else None,
                "name": t.get("name", ""),
                "count": count
            })

    total_briefings = len([t for t in transcripts if t.get("transcript")])
    percentage = (briefings_with_term / total_briefings * 100) if total_briefings > 0 else 0

    # Calculate trend (simple: compare first half vs second half)
    trend = "stable"
    if len(mentions_by_date) >= 4:
        mid = len(mentions_by_date) // 2
        first_half_avg = sum(m["count"] for m in mentions_by_date[:mid]) / mid
        second_half_avg = sum(m["count"] for m in mentions_by_date[mid:]) / (len(mentions_by_date) - mid)
        if second_half_avg > first_half_avg * 1.2:
            trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "decreasing"

    return {
        "term": term,
        "total_mentions": total_mentions,
        "briefings_with_term": briefings_with_term,
        "total_briefings": total_briefings,
        "percentage": round(percentage, 2),
        "trend": trend,
        "mentions_by_date": sorted(mentions_by_date, key=lambda x: x.get("date") or "", reverse=True)
    }


def calculate_all_term_frequencies(
    transcripts: list[dict[str, Any]],
    min_frequency: int = 5,
    max_terms: int = 500,
    speakers: list[str] | None = None
) -> list[dict[str, Any]]:
    """Calculate frequency of all terms across transcripts (optionally for specific speakers only)."""
    word_counts: Counter = Counter()
    word_briefing_counts: Counter = Counter()
    total_briefings = 0

    # Common words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
        'that', 'this', 'these', 'those', 'it', 'its', 'i', 'you', 'he',
        'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
        'his', 'our', 'their', 'what', 'which', 'who', 'whom', 'whose',
        'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
        'now', 'here', 'there', 'then', 'if', 'because', 'about', 'into',
        'through', 'during', 'before', 'after', 'above', 'below', 'up',
        'down', 'out', 'off', 'over', 'under', 'again', 'further', 'once',
        'any', 'being', 'going', 'get', 'got', 'know', 'think', 'want',
        'said', 'say', 'says', 'like', 'well', 'back', 'one', 'two',
        'yeah', 'yes', 'okay', 'right', 'really', 'very', 'much', 'many'
    }

    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            continue

        total_briefings += 1
        text_to_analyze = filter_by_speakers(transcript_text, speakers) if speakers else transcript_text
        cleaned = clean_text(text_to_analyze).lower()

        # Tokenize and count
        words = word_tokenize(cleaned)
        words = [w for w in words if w.isalpha() and len(w) > 2 and w not in stop_words]

        word_counts.update(words)
        word_briefing_counts.update(set(words))  # Count each word once per briefing

    # Build result list
    results = []
    for word, count in word_counts.most_common(max_terms):
        if count >= min_frequency:
            briefing_count = word_briefing_counts[word]
            percentage = (briefing_count / total_briefings * 100) if total_briefings > 0 else 0
            results.append({
                "term": word,
                "count": count,
                "briefings_with_term": briefing_count,
                "total_briefings": total_briefings,
                "percentage": round(percentage, 2)
            })

    return results


def extract_ngrams(
    transcripts: list[dict[str, Any]],
    n: int = 2,
    min_frequency: int = 3,
    max_ngrams: int = 200,
    speakers: list[str] | None = None
) -> list[dict[str, Any]]:
    """Extract n-grams (phrases) from transcripts (optionally for specific speakers only)."""
    ngram_counts: Counter = Counter()
    ngram_briefing_counts: Counter = Counter()
    total_briefings = 0

    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            continue

        total_briefings += 1
        text_to_analyze = filter_by_speakers(transcript_text, speakers) if speakers else transcript_text
        cleaned = clean_text(text_to_analyze).lower()

        # Tokenize
        words = word_tokenize(cleaned)
        words = [w for w in words if w.isalpha()]

        # Generate n-grams
        grams = list(nltk_ngrams(words, n))
        gram_strings = [' '.join(gram) for gram in grams]

        ngram_counts.update(gram_strings)
        ngram_briefing_counts.update(set(gram_strings))

    # Build result list
    results = []
    for phrase, count in ngram_counts.most_common(max_ngrams):
        if count >= min_frequency:
            briefing_count = ngram_briefing_counts[phrase]
            percentage = (briefing_count / total_briefings * 100) if total_briefings > 0 else 0
            results.append({
                "phrase": phrase,
                "count": count,
                "briefings_with_phrase": briefing_count,
                "total_briefings": total_briefings,
                "percentage": round(percentage, 2)
            })

    return results


def search_term_in_context(
    transcripts: list[dict[str, Any]],
    query: str,
    context_chars: int = 200,
    speakers: list[str] | None = None
) -> dict[str, Any]:
    """Search for a term and return matches with surrounding context (optionally for specific speakers only)."""
    matches: list[dict[str, Any]] = []
    total_count = 0

    query_lower = query.lower()
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            continue

        text_to_search = filter_by_speakers(transcript_text, speakers) if speakers else transcript_text

        # Find all matches
        for match in pattern.finditer(text_to_search):
            start = max(0, match.start() - context_chars)
            end = min(len(text_to_search), match.end() + context_chars)

            context = text_to_search[start:end]
            # Clean up context edges
            if start > 0:
                context = "..." + context
            if end < len(text_to_search):
                context = context + "..."

            total_count += 1
            matches.append({
                "transcript_id": t.get("id"),
                "transcript_name": t.get("name", ""),
                "date": t.get("created_at", "")[:10] if t.get("created_at") else None,
                "context": context,
                "position": match.start()
            })

    # Group matches by transcript
    transcripts_with_matches = len(set(m["transcript_id"] for m in matches))

    return {
        "query": query,
        "total_matches": total_count,
        "transcripts_with_matches": transcripts_with_matches,
        "matches": matches[:100]  # Limit to first 100 matches
    }


