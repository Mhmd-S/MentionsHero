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

def normalize_text(text: str) -> str:
    """Normalize unicode characters for consistent matching.

    Converts curly quotes/apostrophes to straight versions and
    typographic dashes to plain hyphens so regex patterns match reliably.
    """
    text = text.replace('\u2019', "'")   # right single quote → apostrophe
    text = text.replace('\u2018', "'")   # left single quote → apostrophe
    text = text.replace('\u201c', '"')   # left double quote
    text = text.replace('\u201d', '"')   # right double quote
    text = text.replace('\u2013', '-')   # en-dash → hyphen
    text = text.replace('\u2014', '-')   # em-dash → hyphen
    return text


def _build_single_word_pattern(word: str) -> str:
    """Build regex for a single word with plural and possessive variants.

    Only matches the base word, its plural, and possessive forms.
    No verb conjugations (-ed, -ing).
    """
    escaped = re.escape(word)
    # Make periods optional for abbreviations (Mr. → Mr)
    escaped = escaped.replace(r'\.', r'\.?')

    poss = r"(?:'s)?"

    # Consonant+y: ally → allies
    if re.search(r'[^aeiou]y$', word, re.IGNORECASE):
        base = escaped[:-1]  # strip 'y'
        return (
            r"\b(?:"
            + escaped + poss
            + r"|" + base + r"ies" + poss
            + r")\b"
        )

    # Words ending in s, sh, ch, x, z take +es plural; others take +s
    if re.search(r'(?:s|sh|ch|x|z)$', word, re.IGNORECASE):
        plural_suffix = r"es"
    else:
        plural_suffix = r"s"
    return (
        r"\b(?:"
        + escaped + poss
        + r"|" + escaped + plural_suffix + poss
        + r")\b"
    )


def _build_compound_pattern(words: list[str]) -> str:
    """Build regex for multi-word terms with space/hyphen/joined variants.

    'shut down' matches 'shut down', 'shut-down', and 'shutdown'.
    'Mr Speaker' matches 'Mr. Speaker' and vice versa (optional periods between words).
    Only plural/possessive suffixes are added (no -ed/-ing on compounds).
    """
    # Strip trailing periods from words (handled by \.? separators)
    cleaned_words = [w.rstrip('.') for w in words]
    escaped_words = [re.escape(w) for w in cleaned_words]
    suffix = r"(?:'?s)?"

    # Spaced form: Mr\.?\s+Speaker (optional period after each word for abbreviations)
    spaced = r"\.?\s+".join(escaped_words) + suffix
    # Hyphenated form: shut-down
    hyphenated = r"\.?\-".join(escaped_words) + suffix

    forms = [spaced, hyphenated]

    # Joined form only for 2-word terms: shutdown
    if len(words) == 2:
        joined = "".join(escaped_words) + suffix
        forms.append(joined)

    return r"\b(?:" + r"|".join(forms) + r")\b"


def build_market_pattern(term: str) -> str:
    """Build regex pattern matching a term with plural and possessive variants.

    Handles:
    - Plural forms (+s, +es, y→ies)
    - Possessive forms (+'s)
    - Compound terms: space/hyphen/joined variants (shut down ↔ shutdown)
    - Abbreviation periods: Mr. matches Mr

    Uses word boundaries to avoid partial matches.
    """
    term = normalize_text(term.strip())
    if not term:
        return r'(?!)'  # never matches

    words = term.split()
    if len(words) > 1:
        return _build_compound_pattern(words)
    return _build_single_word_pattern(term)


def clean_text(text: str) -> str:
    """Clean transcript text for analysis.

    Handles transcript format like:
        Caroline:
        Look, it's true that...

        Reporter:
        Thank you, Caroline...
    """
    # Remove speaker labels at the start of lines
    # Pattern matches: start of line, optional whitespace, speaker name, colon, optional whitespace/newline
    # Using broad pattern: [A-Z0-9] start, allowed chars, max 60 chars
    text = re.sub(r'^\s*[A-Z0-9][\w\s\-\'._()]{1,60}?:\s*\n?', '', text, flags=re.MULTILINE)

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

    # Pattern: optional [MM:SS] timestamp, then speaker name followed by colon
    # Supports: "[00:00] Gabe:", "Caroline:", "[12:34] SPEAKER_00:"
    # Max length 60
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
        transcript_id = t.get("id") or t.get("name") or ""
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
        text_to_search = text_to_analyze if case_sensitive else text_to_analyze.lower()
        text_to_search = normalize_text(text_to_search)

        # Count occurrences (market resolution rules: plurals, possessives, compounds)
        count = len(re.findall(build_market_pattern(search_term), text_to_search))

        if count > 0:
            briefings_with_term += 1
            total_mentions += count
            # Use upload_date (YouTube upload) if available, format YYYYMMDD -> YYYY-MM-DD
            upload_date = t.get("upload_date")
            if upload_date and len(upload_date) == 8:
                formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
            else:
                formatted_date = None
            mentions_by_date.append({
                "date": formatted_date,
                "name": t.get("name") or "Unknown",
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


def group_nearby_mentions(
    matches: list[dict[str, Any]],
    proximity_chars: int = 800,
) -> list[dict[str, Any]]:
    """
    Group matches within the same transcript that are within proximity_chars of each other.
    Merges their context strings into one block.

    Input matches have: transcript_id, transcript_name, date, context, position
    Returns clusters: transcript_id, transcript_name, date, merged_context, mention_count, positions
    """
    # Group by transcript first
    by_transcript: dict[str, list[dict[str, Any]]] = {}
    for m in matches:
        tid = m.get("transcript_id") or ""
        by_transcript.setdefault(tid, []).append(m)

    clusters: list[dict[str, Any]] = []

    for tid, transcript_matches in by_transcript.items():
        # Sort by position
        sorted_matches = sorted(transcript_matches, key=lambda x: x.get("position", 0))

        current_cluster: list[dict[str, Any]] = [sorted_matches[0]]

        for m in sorted_matches[1:]:
            last_pos = current_cluster[-1].get("position", 0)
            cur_pos = m.get("position", 0)

            if cur_pos - last_pos <= proximity_chars:
                current_cluster.append(m)
            else:
                # Emit current cluster
                clusters.append(_build_cluster(current_cluster))
                current_cluster = [m]

        # Emit final cluster
        clusters.append(_build_cluster(current_cluster))

    return clusters


def _build_cluster(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a cluster dict from a list of nearby matches."""
    first = matches[0]
    contexts = [m.get("context", "") for m in matches]
    # Merge contexts: join with separator, deduplicate overlapping text
    merged = "\n---\n".join(contexts)
    return {
        "transcript_id": first.get("transcript_id"),
        "transcript_name": first.get("transcript_name", "Unknown"),
        "date": first.get("date"),
        "merged_context": merged,
        "mention_count": sum(m.get("mention_count", 1) for m in matches),
        "positions": [m.get("position", 0) for m in matches],
    }


def search_term_in_context(
    transcripts: list[dict[str, Any]],
    query: str,
    context_chars: int = 200,
    speakers: list[str] | None = None
) -> dict[str, Any]:
    """Search for a term and return matches with surrounding context (optionally for specific speakers only)."""
    matches: list[dict[str, Any]] = []
    total_count = 0

    pattern = re.compile(build_market_pattern(query), re.IGNORECASE)

    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            continue

        text_to_search = filter_by_speakers(transcript_text, speakers) if speakers else transcript_text
        text_to_search = normalize_text(text_to_search)

        # Collect all match spans, then merge overlapping context windows
        raw_spans = []
        for match in pattern.finditer(text_to_search):
            ctx_start = max(0, match.start() - context_chars)
            ctx_end = min(len(text_to_search), match.end() + context_chars)
            raw_spans.append((ctx_start, ctx_end, match.start()))

        if not raw_spans:
            continue

        # Merge overlapping spans
        raw_spans.sort()
        merged = [list(raw_spans[0])]
        mention_counts = [1]
        for ctx_start, ctx_end, pos in raw_spans[1:]:
            if ctx_start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], ctx_end)
                mention_counts[-1] += 1
            else:
                merged.append([ctx_start, ctx_end, pos])
                mention_counts.append(1)

        # Use upload_date (YouTube upload) if available, format YYYYMMDD -> YYYY-MM-DD
        upload_date = t.get("upload_date")
        if upload_date and len(upload_date) == 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        else:
            formatted_date = None

        total_count += len(raw_spans)
        for (start, end, pos), mention_count in zip(merged, mention_counts):
            context = text_to_search[start:end]
            if start > 0:
                context = "..." + context
            if end < len(text_to_search):
                context = context + "..."
            matches.append({
                "transcript_id": t.get("id"),
                "transcript_name": t.get("name") or "Unknown",
                "date": formatted_date,
                "context": context,
                "position": pos,
                "mention_count": mention_count,
            })

    # Group matches by transcript
    transcripts_with_matches = len(set(m["transcript_id"] for m in matches))

    return {
        "query": query,
        "total_matches": total_count,
        "transcripts_with_matches": transcripts_with_matches,
        "matches": matches[:100]  # Limit to first 100 matches
    }


