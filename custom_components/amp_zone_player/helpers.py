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


def sound_mode_entity_candidates(zone_id: str) -> list[str]:
    """Ordered media_player ids to try for select_sound_mode on a digital zone.

    MA AirPlay/Cast proxies (``*_str``, ``*_ma``, …) often lack sound modes; the
    Songpal/AVR ``*_receiver`` sibling usually has them.
    """
    if not zone_id or "." not in zone_id:
        return []
    domain, object_id = zone_id.split(".", 1)
    candidates = [zone_id]
    for suffix in ("_str", "_ma", "_airplay", "_cast"):
        if object_id.endswith(suffix):
            base = object_id[: -len(suffix)]
            if base:
                candidates.append(f"{domain}.{base}_receiver")
            break
    else:
        candidates.append(f"{domain}.{object_id}_receiver")
    out: list[str] = []
    for entity_id in candidates:
        if entity_id and entity_id not in out:
            out.append(entity_id)
    return out


def resolve_sound_mode_entity(
    zone_id: str,
    sound_mode: str,
    sound_mode_lists: dict[str, list[str] | None],
) -> str:
    """Pick the entity that can apply ``sound_mode`` (prefer exact list match)."""
    candidates = sound_mode_entity_candidates(zone_id)
    fallback = zone_id
    for entity_id in candidates:
        modes = sound_mode_lists.get(entity_id)
        if not modes:
            continue
        if sound_mode in modes:
            return entity_id
        if fallback == zone_id and entity_id != zone_id:
            fallback = entity_id
    return fallback


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


def digital_join_members(zone_id: str, already: list[str] | None) -> list[str]:
    """Zone ids to send on a decoder join: current digital members, then this one.

    Some players replace SyncGroup membership with ``group_members`` instead of
    adding. Sending only the new receiver would drop the others.
    """
    members: list[str] = []
    for entity_id in already or []:
        if entity_id and entity_id not in members:
            members.append(entity_id)
    if zone_id and zone_id not in members:
        members.append(zone_id)
    return members


def wiim_native_unique_id(unique_id: str | None) -> str | None:
    """Music Assistant ``wiim_uuid:`` id → native WiiM unique id (first 12 bytes)."""
    if not unique_id:
        return None
    raw = unique_id.strip()
    prefix = "wiim_uuid:"
    if raw.lower().startswith(prefix):
        raw = raw[len(prefix) :]
    hexchars = "".join(ch for ch in raw if ch in "0123456789abcdefABCDEF")
    if len(hexchars) < 24:
        return None
    return hexchars[:24].upper()


def digital_zone_in_sync_group(
    zone_id: str,
    decoder_id: str,
    playback_id: str,
    decoder_members: list[str] | None,
    playback_members: list[str] | None,
    zone_members: list[str] | None,
) -> bool:
    """True when a digital receiver is still grouped with the decoder SyncGroup."""
    for members in (decoder_members, playback_members):
        if members and zone_id in members:
            return True
    if zone_members and (
        decoder_id in zone_members or playback_id in zone_members
    ):
        return True
    return False
