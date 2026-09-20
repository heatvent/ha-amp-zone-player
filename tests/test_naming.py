"""Tests for facade display naming (no Home Assistant required)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "amp_zone_player"))

from naming import strip_amp_prefix  # noqa: E402


def test_strip_control4_amp_prefix():
    assert strip_amp_prefix("Control4 Amp Bar Speakers") == "Bar Speakers"
    assert strip_amp_prefix("Control4 Amp Dining Room Speakers") == "Dining Room Speakers"
    assert strip_amp_prefix("Control4 Amp Kitchen Speakers") == "Kitchen Speakers"


def test_strip_variants():
    assert strip_amp_prefix("C4 Amp Patio Speakers") == "Patio Speakers"
    assert strip_amp_prefix("Control 4 Amp Garage Speakers") == "Garage Speakers"
    assert strip_amp_prefix("Kitchen") == "Kitchen"
