"""Short display names for facade media players."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

# "Control4 Amp Bar Speakers" → "Bar Speakers"
# Also strips a leading device title like "Control4 Amplifier Zones ".
_ZONE_PREFIX = re.compile(
    r"^(?:"
    r"Control\s*4\s+Amp(?:lifier)?(?:\s+Zones?)?\s+"
    r"|Control\s*4\s+"
    r"|C4\s+Amp\s+"
    r"|C4\s+"
    r"|Amp\s+"
    r")",
    re.IGNORECASE,
)

# Leading slug tokens to drop from zone entity_ids.
_SLUG_DROP = {
    "control4",
    "c4",
    "amp",
    "amp3",
    "16amp3",
    "amplifier",
    "zones",
    "zone",
    "media",
    "closet",
}

_SLUGIFY = re.compile(r"[^a-z0-9]+")


def friendly_name(state: State | None, entity_id: str) -> str:
    if state is None:
        return entity_id.split(".", 1)[-1].replace("_", " ").title()
    return state.name or entity_id


def strip_amp_prefix(name: str) -> str:
    cleaned = name.strip()
    for _ in range(3):
        nxt = _ZONE_PREFIX.sub("", cleaned).strip()
        if nxt == cleaned:
            break
        cleaned = nxt
    return cleaned or name.strip()


def short_from_entity_id(entity_id: str) -> str | None:
    """media_player.media_closet_control4_amp_bar_speakers → Bar Speakers."""
    slug = entity_id.partition(".")[2]
    if not slug:
        return None
    parts = [p for p in slug.split("_") if p]
    while parts and parts[0].lower() in _SLUG_DROP:
        parts.pop(0)
    # Drop trailing numeric suffixes from HA collisions (_2).
    while parts and parts[-1].isdigit():
        parts.pop()
    if not parts:
        return None
    return " ".join(part.capitalize() for part in parts)


def short_zone_label(hass: HomeAssistant, zone_entity_id: str) -> str:
    """
    Short room label for HA and Music Assistant.

    Prefer the zone entity id / stripped zone name (e.g. Bar Speakers) over the
    HA area name (often just Bar). Never include the MAZP hub/device title.
    """
    from_id = short_from_entity_id(zone_entity_id)
    if from_id:
        return from_id

    raw = friendly_name(hass.states.get(zone_entity_id), zone_entity_id)
    stripped = strip_amp_prefix(raw)
    if stripped:
        return stripped

    return raw


def facade_name(hass: HomeAssistant, zone_entity_id: str, name_prefix: str) -> str:
    """Build the HA/MA display name. Prefix is optional and off by default."""
    base = short_zone_label(hass, zone_entity_id)
    prefix = (name_prefix or "").strip()
    if not prefix:
        return base
    return f"{prefix} {base}".strip()


def facade_object_id(label: str) -> str:
    """Stable short object id: Bar Speakers → mazp_bar_speakers."""
    slug = _SLUGIFY.sub("_", label.lower()).strip("_")
    if not slug:
        slug = "zone"
    return f"mazp_{slug}"
