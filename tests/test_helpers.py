"""Unit tests for helpers (no Home Assistant required)."""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "amp_zone_player")
)

from helpers import (  # noqa: E402
    SOURCE_NONE,
    entry_unique_id,
    map_player_state,
    normalize_playback,
    normalize_sound_mode,
    normalize_source,
    normalize_zones,
    source_form_value,
)


def test_normalize_zones():
    assert normalize_zones("media_player.a") == ["media_player.a"]
    assert normalize_zones(["media_player.a", "media_player.b"]) == [
        "media_player.a",
        "media_player.b",
    ]
    assert normalize_zones(None) == []
    assert normalize_zones("") == []


def test_normalize_source():
    assert normalize_source(None) == ""
    assert normalize_source("") == ""
    assert normalize_source(SOURCE_NONE) == ""
    assert normalize_source("  WiiM Pro  ") == "WiiM Pro"


def test_normalize_playback():
    assert normalize_playback(None) == ""
    assert normalize_playback("  media_player.house  ") == "media_player.house"


def test_normalize_sound_mode():
    assert normalize_sound_mode(None) == ""
    assert normalize_sound_mode("  Multi Stereo  ") == "Multi Stereo"


def test_source_form_value():
    assert source_form_value("") == SOURCE_NONE
    assert source_form_value(None) == SOURCE_NONE
    assert source_form_value("WiiM Pro") == "WiiM Pro"


def test_entry_unique_id():
    assert (
        entry_unique_id("media_player.wiim", ["media_player.b", "media_player.a"])
        == "media_player.wiim|media_player.a|media_player.b"
    )
    assert (
        entry_unique_id(
            "media_player.wiim",
            ["media_player.a"],
            ["media_player.sony"],
        )
        == "media_player.wiim|media_player.a|d:media_player.sony"
    )


def test_map_player_state_standby_to_idle():
    assert map_player_state("standby") == "idle"
    assert map_player_state("playing") == "playing"
    assert map_player_state("unknown") is None
