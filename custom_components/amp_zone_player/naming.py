"""Short display names for facade media players."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

# "Control4 Amp Bar Speakers" → "Bar Speakers"
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

_HAS_SPEAKERS = re.compile(r"speakers?$", re.IGNORECASE)

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
    while parts and parts[-1].isdigit():
        parts.pop()
    if not parts:
        return None
    return " ".join(part.capitalize() for part in parts)


def with_speakers_suffix(label: str) -> str:
    """Amp zones are always speakers — keep/restore the Speakers suffix."""
    label = label.strip()
    if not label:
        return label
    if _HAS_SPEAKERS.search(label):
        return label
    return f"{label} Speakers"


def _candidate_score(label: str) -> tuple[int, int, int]:
    """Prefer labels that already include Speakers and are more descriptive."""
    parts = len(label.split())
    has_sp = 1 if _HAS_SPEAKERS.search(label) else 0
    return (has_sp, parts, len(label))


def short_zone_label(hass: HomeAssistant, zone_entity_id: str) -> str:
    """
    Short room label for HA and Music Assistant (e.g. Bar Speakers).

    Uses the linked Control4 zone's names / entity id — never the MAZP hub title
    and never a bare area name like "Bar" when Speakers belongs on the label.
    """
    from homeassistant.helpers import entity_registry as er

    candidates: list[str] = []

    ent = er.async_get(hass).async_get(zone_entity_id)
    if ent is not None:
        for raw in (ent.original_name, ent.name):
            if raw:
                candidates.append(strip_amp_prefix(str(raw)))

    state = hass.states.get(zone_entity_id)
    candidates.append(strip_amp_prefix(friendly_name(state, zone_entity_id)))

    from_id = short_from_entity_id(zone_entity_id)
    if from_id:
        candidates.append(from_id)

    cleaned = [c.strip() for c in candidates if c and c.strip()]
    if not cleaned:
        cleaned = [zone_entity_id.split(".", 1)[-1].replace("_", " ").title()]

    best = max(cleaned, key=_candidate_score)
    return with_speakers_suffix(best)


def facade_name(hass: HomeAssistant, zone_entity_id: str, name_prefix: str) -> str:
    """Build the HA/MA display name. Prefix is optional and off by default."""
    base = short_zone_label(hass, zone_entity_id)
    prefix = (name_prefix or "").strip()
    if not prefix:
        return base
    return f"{prefix} {base}".strip()


def facade_object_id(label: str) -> str:
    """Stable short object id: Bar Speakers → bar_speakers."""
    slug = _SLUGIFY.sub("_", label.lower()).strip("_")
    if not slug:
        slug = "zone"
    return slug
