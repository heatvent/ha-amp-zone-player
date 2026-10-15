"""Tests for facade display naming (no Home Assistant required)."""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "amp_zone_player")
)

from naming import (  # noqa: E402
    facade_object_id,
    room_speakers_label,
    short_from_entity_id,
    strip_amp_prefix,
    strip_paren_suffix,
    strip_receiver_suffix,
    with_speakers_suffix,
)


def test_strip_and_speakers():
    assert strip_amp_prefix("Control4 Amp Bar Speakers") == "Bar Speakers"
    assert with_speakers_suffix("Bar") == "Bar Speakers"
    assert with_speakers_suffix("Bar Speakers") == "Bar Speakers"
    assert with_speakers_suffix("Dining Room") == "Dining Room Speakers"


def test_receiver_to_speakers_label():
    assert strip_receiver_suffix("Living Room STR") == "Living Room"
    assert strip_receiver_suffix("Theater STR-AZ1000ES") == "Theater"
    assert room_speakers_label("Living Room STR") == "Living Room Speakers"
    assert room_speakers_label("Theater STR") == "Theater Speakers"
    assert room_speakers_label("Bar Speakers") == "Bar Speakers"


def test_paren_suffix_c4_amp_tag():
    assert strip_paren_suffix("Bar Speakers (C4 amp)") == "Bar Speakers"
    assert room_speakers_label("Bar Speakers (C4 amp)") == "Bar Speakers"
    assert facade_object_id(room_speakers_label("Kitchen Speakers (C4 amp)")) == (
        "kitchen_speakers"
    )


def test_short_from_entity_id():
    assert (
        short_from_entity_id("media_player.media_closet_control4_amp_bar_speakers")
        == "Bar Speakers"
    )
    assert short_from_entity_id("media_player.bar") == "Bar"
    assert short_from_entity_id("media_player.living_room_str") == "Living Room"


def test_facade_object_id():
    assert facade_object_id("Bar Speakers") == "bar_speakers"
