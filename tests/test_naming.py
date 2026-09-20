"""Tests for facade display naming (no Home Assistant required)."""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "amp_zone_player")
)

# naming.py imports homeassistant; stub only what strip/entity_id helpers need.
import naming as naming_mod  # noqa: E402


def test_strip_control4_amp_prefix():
    assert naming_mod.strip_amp_prefix("Control4 Amp Bar Speakers") == "Bar Speakers"
    assert (
        naming_mod.strip_amp_prefix("Control4 Amp Dining Room Speakers")
        == "Dining Room Speakers"
    )


def test_strip_concatenated_device_and_zone():
    assert (
        naming_mod.strip_amp_prefix(
            "Control4 Amplifier Zones Control4 Amp Bar Speakers"
        )
        == "Bar Speakers"
    )


def test_short_from_entity_id():
    assert (
        naming_mod.short_from_entity_id(
            "media_player.media_closet_control4_amp_bar_speakers"
        )
        == "Bar Speakers"
    )
    assert (
        naming_mod.short_from_entity_id("media_player.control4_amp_kitchen_speakers")
        == "Kitchen Speakers"
    )
