"""Tests for facade display naming (no Home Assistant required)."""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "amp_zone_player")
)

from naming import (  # noqa: E402
    facade_object_id,
    short_from_entity_id,
    strip_amp_prefix,
    with_speakers_suffix,
)


def test_strip_and_speakers():
    assert strip_amp_prefix("Control4 Amp Bar Speakers") == "Bar Speakers"
    assert with_speakers_suffix("Bar") == "Bar Speakers"
    assert with_speakers_suffix("Bar Speakers") == "Bar Speakers"
    assert with_speakers_suffix("Dining Room") == "Dining Room Speakers"


def test_short_from_entity_id():
    assert (
        short_from_entity_id("media_player.media_closet_control4_amp_bar_speakers")
        == "Bar Speakers"
    )
    assert short_from_entity_id("media_player.bar") == "Bar"


def test_facade_object_id():
    assert facade_object_id("Bar Speakers") == "bar_speakers"
