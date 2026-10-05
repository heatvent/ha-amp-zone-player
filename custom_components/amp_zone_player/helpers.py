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


def normalize_zones(zones: str | list[str] | None) -> list[str]:
    if zones is None:
        return []
    if isinstance(zones, str):
        return [zones] if zones.strip() else []
    return [z for z in zones if isinstance(z, str) and z.strip()]


def normalize_source(value: str | None) -> str:
    """Stored source name; blank means leave zone source as-is."""
    raw = (value or "").strip()
    if not raw or raw == SOURCE_NONE:
        return ""
    return raw


def normalize_playback(value: str | None) -> str:
    """Optional queue owner; blank means use decoder."""
    return (value or "").strip()


def normalize_sound_mode(value: str | None) -> str:
    """Optional digital-zone sound mode; blank means do not change."""
    return (value or "").strip()


def source_form_value(stored: str | None) -> str:
    """Select option value for a previously saved source."""
    raw = (stored or "").strip()
    return raw if raw else SOURCE_NONE


def entry_unique_id(
    decoder: str,
    zones: list[str],
    digital_zones: list[str] | None = None,
) -> str:
    parts = [decoder, *sorted(zones)]
    digital = normalize_zones(digital_zones)
    if digital:
        parts.extend(f"d:{z}" for z in sorted(digital))
    return "|".join(parts)


def map_player_state(raw: str | None) -> str | None:
    """Map a media_player state string to a supported MediaPlayerState value."""
    if raw is None:
        return None
    return STATE_MAP.get(raw)
