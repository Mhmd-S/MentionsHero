"""Unit tests for event-time derivation (pure, no API).

Covers compute_event_time's priority ladder and _parse_iso's normalization.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.metadata_extraction_service import _parse_iso, compute_event_time

# Two distinct epochs so "which source won" is unambiguous in assertions.
RELEASE_EPOCH = 1_700_000_000   # 2023-11-14T22:13:20Z
UPLOAD_EPOCH = 1_700_009_999    # ~2.7h later
LLM_ISO = "2026-05-07T15:47:00Z"


def test_live_release_timestamp_wins_over_everything():
    dt = compute_event_time(
        was_live=True,
        release_timestamp=RELEASE_EPOCH,
        timestamp=UPLOAD_EPOCH,
        llm_event_datetime=LLM_ISO,
    )
    assert dt == datetime.fromtimestamp(RELEASE_EPOCH, tz=timezone.utc)
    assert dt.tzinfo is not None and dt.utcoffset() == timedelta(0)


def test_release_ignored_when_not_live():
    # Not a livestream: release_timestamp must NOT be used; llm is next priority.
    dt = compute_event_time(
        was_live=False,
        release_timestamp=RELEASE_EPOCH,
        timestamp=UPLOAD_EPOCH,
        llm_event_datetime=LLM_ISO,
    )
    assert dt == _parse_iso(LLM_ISO)


def test_llm_datetime_beats_upload_timestamp():
    dt = compute_event_time(
        was_live=False,
        release_timestamp=None,
        timestamp=UPLOAD_EPOCH,
        llm_event_datetime=LLM_ISO,
    )
    assert dt == _parse_iso(LLM_ISO)


def test_falls_back_to_upload_timestamp():
    dt = compute_event_time(
        was_live=False, release_timestamp=None, timestamp=UPLOAD_EPOCH, llm_event_datetime=None
    )
    assert dt == datetime.fromtimestamp(UPLOAD_EPOCH, tz=timezone.utc)


def test_live_but_no_release_falls_through_to_upload():
    dt = compute_event_time(
        was_live=True, release_timestamp=None, timestamp=UPLOAD_EPOCH, llm_event_datetime=None
    )
    assert dt == datetime.fromtimestamp(UPLOAD_EPOCH, tz=timezone.utc)


def test_invalid_release_timestamp_falls_through():
    # An absurd epoch makes fromtimestamp raise; it must be caught and we fall
    # through to the next available source rather than crashing.
    dt = compute_event_time(
        was_live=True,
        release_timestamp=10**18,
        timestamp=UPLOAD_EPOCH,
        llm_event_datetime=None,
    )
    assert dt == datetime.fromtimestamp(UPLOAD_EPOCH, tz=timezone.utc)


def test_nothing_available_returns_none():
    assert compute_event_time(
        was_live=False, release_timestamp=None, timestamp=None, llm_event_datetime=None
    ) is None


# ---------------------------------------------------------------------------
# _parse_iso
# ---------------------------------------------------------------------------

def test_parse_iso_trailing_z():
    dt = _parse_iso("2026-05-07T15:47:00Z")
    assert dt == datetime(2026, 5, 7, 15, 47, tzinfo=timezone.utc)


def test_parse_iso_explicit_offset_zero():
    assert _parse_iso("2026-05-07T15:47:00+00:00") == datetime(2026, 5, 7, 15, 47, tzinfo=timezone.utc)


def test_parse_iso_naive_assumed_utc():
    dt = _parse_iso("2026-05-07T15:47:00")
    assert dt.tzinfo is not None and dt.utcoffset() == timedelta(0)
    assert dt == datetime(2026, 5, 7, 15, 47, tzinfo=timezone.utc)


def test_parse_iso_preserves_nonzero_offset():
    dt = _parse_iso("2026-05-07T10:00:00-05:00")
    assert dt.utcoffset() == timedelta(hours=-5)
    # ...and it's the same instant as 15:00Z
    assert dt == datetime(2026, 5, 7, 15, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", [None, "", "   ", "not-a-date", "2026-13-45T99:99:99Z"])
def test_parse_iso_bad_values_return_none(value):
    assert _parse_iso(value) is None
