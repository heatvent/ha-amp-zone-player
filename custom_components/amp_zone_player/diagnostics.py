"""Diagnostics for Music Assistant Amp Zone Player."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DECODER,
    CONF_NAME_PREFIX,
    CONF_PLAYBACK,
    CONF_SOURCE,
    CONF_ZONES,
    DOMAIN,
)
from .helpers import normalize_source


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = {**entry.data, **entry.options}
    decoder = data.get(CONF_DECODER)
    zones = list(data.get(CONF_ZONES) or [])
    playback = (data.get(CONF_PLAYBACK) or "").strip() or None
    source = normalize_source(data.get(CONF_SOURCE))

    zone_states: dict[str, Any] = {}
    for zone_id in zones:
        state = hass.states.get(zone_id)
        if state is None:
            zone_states[zone_id] = {"state": None}
            continue
        source_list = state.attributes.get("source_list") or []
        zone_states[zone_id] = {
            "state": state.state,
            "source": state.attributes.get("source"),
            "volume_level": state.attributes.get("volume_level"),
            "source_list": list(source_list) if isinstance(source_list, list) else [],
            "source_in_list": (
                (not source) or (source in source_list)
                if isinstance(source_list, list)
                else None
            ),
        }

    decoder_state = hass.states.get(decoder) if decoder else None
    playback_state = hass.states.get(playback) if playback else None
    session = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    return {
        "entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "version": entry.version,
        },
        "config": {
            CONF_DECODER: decoder,
            CONF_ZONES: zones,
            CONF_SOURCE: source or None,
            CONF_PLAYBACK: playback,
            CONF_NAME_PREFIX: data.get(CONF_NAME_PREFIX) or "",
        },
        "decoder": {
            "entity_id": decoder,
            "state": decoder_state.state if decoder_state else None,
            "attributes": _safe_media_attrs(decoder_state),
        },
        "playback": {
            "entity_id": playback or decoder,
            "state": (
                playback_state.state
                if playback_state
                else (decoder_state.state if decoder_state else None)
            ),
        },
        "zones": zone_states,
        "session": {
            "leader_id": getattr(session, "leader_id", None) if session else None,
            "members": list(getattr(session, "members", []) or []) if session else [],
            "facade_ids": (
                sorted(session.known_facade_ids()) if session else []
            ),
        },
    }


def _safe_media_attrs(state) -> dict[str, Any]:
    if state is None:
        return {}
    keys = (
        "media_title",
        "media_artist",
        "media_content_id",
        "media_content_type",
        "source",
        "group_members",
    )
    return {key: state.attributes.get(key) for key in keys if key in state.attributes}
