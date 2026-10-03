"""Pure helpers (safe to unit-test without Home Assistant)."""

from __future__ import annotations

SOURCE_NONE = "__none__"

# HA state string → MediaPlayerState value (STANDBY removed in HA 2026.8).
STATE_MAP = {
    "off": "off",
    "on": "on",
    "playing": "playing",
    "paused": "paused",
    "idle": "idle",
    "standby": "idle",
}


def normalize_zones(zones: str | list[str]) -> list[str]:
    if isinstance(zones, str):
        return [zones]
    return list(zones)


def normalize_source(value: str | None) -> str:
    """Stored source name; blank means leave zone source as-is."""
    raw = (value or "").strip()
    if not raw or raw == SOURCE_NONE:
        return ""
    return raw


def normalize_playback(value: str | None) -> str:
    """Optional queue owner; blank means use decoder."""
    return (value or "").strip()


def source_form_value(stored: str | None) -> str:
    """Select option value for a previously saved source."""
    raw = (stored or "").strip()
    return raw if raw else SOURCE_NONE


def entry_unique_id(decoder: str, zones: list[str]) -> str:
    return f"{decoder}|{'|'.join(sorted(zones))}"


def map_player_state(raw: str | None) -> str | None:
    """Map a media_player state string to a supported MediaPlayerState value."""
    if raw is None:
        return None
    return STATE_MAP.get(raw)
