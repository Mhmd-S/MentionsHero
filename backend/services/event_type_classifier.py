"""Event-type taxonomy + deterministic title classifier.

Single source of truth for the 16-value event_type taxonomy. Two consumers:

  1. `metadata_extraction_service` — uses `classify_event_type_deterministic(title)`
     as a high-precision guardrail (clear titles get a guaranteed answer without
     the LLM), plus `EVENT_TYPE_DEFINITIONS` as semantic priors in the LLM prompt.
  2. `analytical_event_tag_service` (legacy DDG auto-tagger) — imports
     `EVENT_TYPE_KEYWORDS` to scan DuckDuckGo *result text* (a different input
     than the title), so that dict is kept verbatim from its original form.

The deterministic classifier walks an ORDERED priority list (first match wins),
mirroring the 16-rule order the old title-only prompt used. Priority order IS the
conflict-resolution mechanism — e.g. "Delivers Remarks at the Congressional Ball"
hits both `ceremony` (Ball) and `prepared_remarks` (Delivers Remarks); ceremony is
listed first, so it wins. Returns (None, None) only when no keyword matches at all,
in which case the caller defers to the grounded LLM.
"""

from __future__ import annotations

import re

# The canonical 16-value taxonomy. Mirrors the DB CHECK constraint on
# analytical.event_tags.event_type and the EVENT_TYPES Literal in models/analytical.py.
EVENT_TYPES: list[str] = [
    "rally", "press_conference", "press_briefing", "interview",
    "prepared_remarks", "signing_ceremony", "bilateral_meeting",
    "cabinet_meeting", "reception", "ceremony", "summit", "roundtable",
    "announcement", "greeting", "troop_address", "other",
]

# Semantic, human-readable definition per type — fed to the LLM as priors so it
# classifies on MEANING (using title + description + transcript + grounded search),
# not just keyword presence. Lifted from the Phase-0 spike's EVENT_TYPE_RULES.
EVENT_TYPE_DEFINITIONS: str = """\
- rally: campaign rally, public political gathering with supporters
- press_conference: formal Q&A with press (multi-question, often a major topic); includes press gaggles
- press_briefing: daily / routine press briefing (e.g. Press Secretary at the podium)
- interview: sit-down with a journalist or network
- prepared_remarks: formal speech with prepared text (address to the nation, SOTU, major address, commencement)
- signing_ceremony: bill / executive order / treaty / agreement signing
- bilateral_meeting: meeting with a foreign head of state or foreign delegation
- cabinet_meeting: cabinet or interagency meeting
- reception: themed reception (holiday, heritage month, honoree reception, etc.)
- ceremony: commemorative / celebratory ceremony (holidays, Turkey pardoning, Medal of Honor, awards, swearing-in, tree lighting, state dinner, gala, ball, inauguration)
- summit: multi-stakeholder summit
- roundtable: stakeholder discussion / listening session / task force
- announcement: formal policy / appointment / agency announcement
- greeting: meet-and-greet, photo-op, welcoming guests
- troop_address: speech to or call with the military / service members / troop visit
- other: genuinely fits none of the 15 specific types above
"""

# ---------------------------------------------------------------------------
# Legacy keyword dict — scans DDG RESULT TEXT (body), NOT titles. Kept verbatim
# from analytical_event_tag_service so behaviour is unchanged; that service now
# imports it from here (single source of truth).
# ---------------------------------------------------------------------------
EVENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "rally": ["rally", "campaign event", "campaign rally", "maga rally", "supporters gathered"],
    "press_briefing": [
        "press briefing", "briefs members of the media", "briefs the media",
        "briefing room", "podium", "white house briefing", "press secretary",
    ],
    "press_conference": [
        "press conference", "news conference", "joint press conference", "gaggle",
    ],
    "interview": [
        "interview", "sat down with", "spoke with", "told fox",
        "told cnn", "told msnbc", "told newsmax", "exclusive",
    ],
    "signing_ceremony": [
        "signing ceremony", "bill signing", "signed into law", "signs ",
        "executive order signing",
    ],
    "bilateral_meeting": [
        "bilateral meeting", "bilateral", "meeting with the president",
        "meeting with the prime minister", "meeting with the king",
        "meeting with the chancellor", "meeting with the crown prince",
        "meeting with the secretary general",
    ],
    "cabinet_meeting": ["cabinet meeting"],
    "reception": ["reception"],
    "summit": ["summit"],
    "roundtable": ["roundtable", "task force", "listening session"],
    "announcement": ["announcement", "announces", "makes an announcement"],
    "greeting": ["greeting", "welcomes", "photo op"],
    "troop_address": ["troop visit", "address to the military", "service members"],
    "ceremony": [
        "swearing-in", "swearing in", "medal of honor", "medal presentation",
        "state dinner", "tree lighting", "turkey pardoning",
        "thanksgiving", "halloween", "christmas", "easter",
        "mother's day", "father's day", "veterans day", "memorial day",
        "independence day", "honors", "ball ", "gala", "awards",
    ],
    "prepared_remarks": [
        "state of the union", "address to", "remarks at", "inaugural",
        "teleprompter", "prepared statement", "oval office address",
        "joint session", "commencement",
    ],
}

# Known networks, used to disambiguate "Joins <network>" → interview.
NETWORKS: list[str] = [
    "fox news", "fox business", "fox", "cnn", "msnbc", "nbc", "abc", "cbs",
    "newsmax", "oan", "oann", "bbc", "reuters",
]

# ---------------------------------------------------------------------------
# Deterministic title classifier — ORDERED priority rules (first match wins).
# These are tuned for TITLES (high precision), distinct from EVENT_TYPE_KEYWORDS
# above which scans search-result bodies. Order mirrors the old 16-rule prompt.
# ---------------------------------------------------------------------------

# Rule 2 also matches "(Meeting|Lunch|...) with the (President|King|...) of <X>".
_BILATERAL_PATTERN = (
    r"\b(?:meeting|lunch|dinner|breakfast|tea|working lunch|working dinner) "
    r"with (?:the )?(?:secretary general|president|prime minister|king|queen|"
    r"chancellor|crown prince|ambassador|premier|emir|sultan|chairman|"
    r"foreign minister|director|vice president)\b"
)
# Rule 7 also matches "Joins <network>" / "Sits Down with".
_INTERVIEW_JOINS = r"\bjoins (?:" + "|".join(re.escape(n) for n in NETWORKS) + r")\b"

# Each entry: (event_type, [keyword phrases], [extra raw-regex patterns]).
# Keyword phrases are matched with word boundaries so "signs" ≠ "designs",
# "ball" ≠ "football". Order is significant.
_PRIORITY_RULES: list[tuple[str, list[str], list[str]]] = [
    ("cabinet_meeting", ["cabinet meeting"], []),
    ("bilateral_meeting",
     ["bilateral meeting", "bilateral lunch", "bilateral dinner",
      "bilateral breakfast", "bilateral"],
     [_BILATERAL_PATTERN]),
    ("signing_ceremony",
     ["signing ceremony", "bill signing", "signing with", "signs into law",
      "executive order signing", "signs"], []),
    ("press_conference", ["press conference", "news conference"], []),
    ("press_briefing",
     ["press briefing", "briefs members of the media", "briefs the media"], []),
    ("rally", ["rally"], []),
    ("interview", ["interview", "sits down with", "sit down with", "sat down with"],
     [_INTERVIEW_JOINS]),
    ("reception", ["reception"], []),
    ("roundtable", ["roundtable", "task force", "listening session"], []),
    ("summit", ["summit"], []),
    ("announcement", ["announcement", "makes an announcement", "announces"], []),
    ("greeting", ["greeting", "welcomes", "photo op"], []),
    ("troop_address",
     ["troops", "troop", "address to the military", "service members",
      "service member"], []),
    ("ceremony",
     ["halloween", "easter", "christmas", "thanksgiving", "turkey pardoning",
      "mother's day", "father's day", "veterans day", "memorial day",
      "independence day", "medal of honor", "medal presentation", "honors",
      "state dinner", "hanukkah", "tree lighting", "awards", "swearing-in",
      "swearing in", "ball", "gala", "inauguration"], []),
    ("prepared_remarks",
     ["delivers remarks", "remarks at", "remarks on", "address to", "speech"], []),
]


def _compile(keywords: list[str], extra_patterns: list[str]) -> re.Pattern:
    parts = [r"\b" + re.escape(k) + r"\b" for k in keywords] + list(extra_patterns)
    return re.compile("|".join(parts), re.IGNORECASE)


_COMPILED_RULES: list[tuple[str, re.Pattern]] = [
    (etype, _compile(kws, extra)) for etype, kws, extra in _PRIORITY_RULES
]


def classify_event_type_deterministic(title: str) -> tuple[str | None, str | None]:
    """Classify a video title into an event_type using high-precision keyword rules.

    Returns (event_type, matched_phrase) on the first priority rule that fires,
    or (None, None) when no rule matches (caller defers to the grounded LLM).

    Pure function — no I/O, fully unit-testable.
    """
    if not title or not title.strip():
        return None, None
    text = title.strip()
    for etype, pattern in _COMPILED_RULES:
        m = pattern.search(text)
        if m:
            return etype, m.group(0)
    return None, None
