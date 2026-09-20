"""Tests for facade display naming (no Home Assistant required)."""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "amp_zone_player")
)

from naming import facade_object_id, short_from_entity_id, strip_amp_prefix  # noqa: E402


def test_strip_control4_amp_prefix():
    assert strip_amp_prefix("Control4 Amp Bar Speakers") == "Bar Speakers"
    assert (
        strip_amp_prefix("Control4 Amplifier Zones Control4 Amp Bar Speakers")
        == "Bar Speakers"
    )


def test_short_from_entity_id():
    assert (
        short_from_entity_id("media_player.media_closet_control4_amp_bar_speakers")
        == "Bar Speakers"
    )
    assert (
        short_from_entity_id(
            "media_player.control4_amplifier_zones_control4_amp_bar_speakers_2"
        )
        == "Bar Speakers"
    )


def test_facade_object_id():
    assert facade_object_id("Bar Speakers") == "mazp_bar_speakers"
    assert facade_object_id("Master Bathroom Speakers") == "mazp_master_bathroom_speakers"
