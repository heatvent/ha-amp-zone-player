"""Short display names for facade media players."""

from __future__ import annotations

import re

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er

# "Control4 Amp Bar Speakers" → "Bar Speakers"
_ZONE_PREFIX = re.compile(
    r"^(?:"
    r"Control\s*4\s+Amp\s+"
    r"|Control\s*4\s+"
    r"|C4\s+Amp\s+"
    r"|C4\s+"
    r"|Amp\s+"
    r")",
    re.IGNORECASE,
)


def friendly_name(state: State | None, entity_id: str) -> str:
    if state is None:
        return entity_id.split(".", 1)[-1].replace("_", " ").title()
    return state.name or entity_id


def strip_amp_prefix(name: str) -> str:
    cleaned = _ZONE_PREFIX.sub("", name.strip()).strip()
    return cleaned or name.strip()


def short_zone_label(hass: HomeAssistant, zone_entity_id: str) -> str:
    """
    Prefer the zone's Home Assistant area name.

    Otherwise strip common Control4/amp prefixes from the zone friendly name
    so Music Assistant shows "Bar Speakers" instead of
    "Control4 Amplifier Zones Control4 Amp Bar Speakers".
    """
    ent = er.async_get(hass).async_get(zone_entity_id)
    if ent is not None and ent.area_id:
        area = ar.async_get(hass).async_get_area(ent.area_id)
        if area is not None and area.name:
            return area.name

    raw = friendly_name(hass.states.get(zone_entity_id), zone_entity_id)
    return strip_amp_prefix(raw)


def facade_name(hass: HomeAssistant, zone_entity_id: str, name_prefix: str) -> str:
    base = short_zone_label(hass, zone_entity_id)
    prefix = (name_prefix or "").strip()
    return f"{prefix} {base}".strip() if prefix else base
