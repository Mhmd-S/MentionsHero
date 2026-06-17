"""Unit tests for the deterministic event_type classifier (pure, no API)."""

import pytest

from backend.services.event_type_classifier import (
    EVENT_TYPES,
    classify_event_type_deterministic,
)


@pytest.mark.parametrize(
    "title,expected",
    [
        # --- the documented regression: "Service Members" is a troop_address
        #     trigger that the old title-only LLM call returned as `other`. ---
        ("President Trump Participates in a Call with Service Members", "troop_address"),
        ("President Trump Visits Troops in Qatar", "troop_address"),
        ("President Trump Delivers an Address to the Military", "troop_address"),
        # --- one clear hit per keyword type ---
        ("Cabinet Meeting at the White House", "cabinet_meeting"),
        ("Bilateral Meeting with the Prime Minister of Japan", "bilateral_meeting"),
        ("Working Lunch with the President of France", "bilateral_meeting"),
        ("President Trump Signs Executive Orders", "signing_ceremony"),
        ("Bill Signing Ceremony in the Oval Office", "signing_ceremony"),
        ("President Trump Holds a Press Conference", "press_conference"),
        ("Press Briefing by the Press Secretary", "press_briefing"),
        ("President Trump Holds a Rally in Phoenix, Arizona", "rally"),
        ("President Trump Sits Down with Laura Ingraham", "interview"),
        ("President Trump Joins Fox News for an Interview", "interview"),
        ("President Trump Joins Newsmax", "interview"),
        ("Diwali Reception at the White House", "reception"),
        ("President Trump Hosts a Roundtable on AI", "roundtable"),
        ("President Trump Participates in a Listening Session", "roundtable"),
        ("President Trump Speaks at the World Economic Summit", "summit"),
        ("President Trump Makes an Announcement, Dec. 2, 2025", "announcement"),
        ("President Trump Welcomes the Super Bowl Champions", "greeting"),
        ("President Trump Delivers Remarks to NCAA National Champions", "prepared_remarks"),
        ("President Trump Delivers an Address to the Nation on the Economy", "prepared_remarks"),
        # --- priority: ceremony (#14) MUST beat prepared_remarks (#15) ---
        ("President Trump Delivers Remarks at the Congressional Ball", "ceremony"),
        ("Turkey Pardoning Ceremony", "ceremony"),
        ("National Medal of Honor Presentation", "ceremony"),
        # --- priority: summit (#10) outranks prepared_remarks (#15) ---
        ("President Trump Delivers Remarks at the AI Summit", "summit"),
    ],
)
def test_keyword_titles_classify(title, expected):
    got, signal = classify_event_type_deterministic(title)
    assert got == expected, f"{title!r} -> {got!r} (signal={signal!r})"
    assert signal  # a matched phrase is always returned on a hit


@pytest.mark.parametrize(
    "title",
    [
        # Generic titles with NO keyword — must defer to the LLM (None), not
        # silently become `other`. These are the cases grounding fixes.
        "President Trump Participates in the Champion of Coal Event",
        "Operation Epic Fury Update, President Donald J. Trump",
        "President Trump's administration is cleaning up DC and making America safe",
        # "Addresses" is not the "address to" keyword -> defer, don't guess.
        "President Trump Addresses the Nation",
    ],
)
def test_generic_titles_defer(title):
    assert classify_event_type_deterministic(title) == (None, None)


@pytest.mark.parametrize(
    "title",
    [
        "President Trump Designs a New Policy",   # 'signs' must NOT match 'designs'
        "President Trump Attends a Football Game",  # 'ball' must NOT match 'football'
        "President Trump Visits a Baseball Stadium",  # 'ball' must NOT match 'baseball'
    ],
)
def test_word_boundaries_prevent_false_positives(title):
    assert classify_event_type_deterministic(title) == (None, None)


@pytest.mark.parametrize("title", ["", "   ", None])
def test_empty_titles(title):
    assert classify_event_type_deterministic(title) == (None, None)


def test_returned_type_is_always_in_taxonomy():
    samples = [
        "Cabinet Meeting", "Rally in Ohio", "Press Conference", "Signs the Bill",
        "Christmas Reception", "Bilateral Meeting with the King of Jordan",
    ]
    for s in samples:
        etype, _ = classify_event_type_deterministic(s)
        assert etype in EVENT_TYPES


def test_case_insensitive():
    assert classify_event_type_deterministic("PRESIDENT TRUMP HOLDS A RALLY")[0] == "rally"
    assert classify_event_type_deterministic("cabinet meeting today")[0] == "cabinet_meeting"
