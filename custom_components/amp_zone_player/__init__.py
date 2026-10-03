"""Music Assistant Amp Zone Player — Composer-style sessions over a decoder + amp zones."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, PLATFORMS
from .repairs import async_check_source_issue

SERVICE_TURN_ALL_ZONES_ON = "turn_all_zones_on"
SERVICE_TURN_ALL_ZONES_OFF = "turn_all_zones_off"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""

    if hass.services.has_service(DOMAIN, SERVICE_TURN_ALL_ZONES_ON):
        return

    async def _async_turn_all(call: ServiceCall, *, turn_on: bool) -> None:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        session = hass.data.get(DOMAIN, {}).get(entry_id)
        if session is None:
            raise HomeAssistantError(
                f"No Amp Zone Player session for config entry {entry_id}"
            )
        facades = [
            session.facade_for_entity(entity_id)
            for entity_id in sorted(session.known_facade_ids())
        ]
        for facade in facades:
            if facade is None:
                continue
            if turn_on:
                await facade.async_turn_on()
            else:
                await facade.async_turn_off()

    async def async_turn_all_on(call: ServiceCall) -> None:
        await _async_turn_all(call, turn_on=True)

    async def async_turn_all_off(call: ServiceCall) -> None:
        await _async_turn_all(call, turn_on=False)

    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_ALL_ZONES_ON,
        async_turn_all_on,
        schema=_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_ALL_ZONES_OFF,
        async_turn_all_off,
        schema=_SERVICE_SCHEMA,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Music Assistant Amp Zone Player from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(p) for p in PLATFORMS]
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _when_started(_hass: HomeAssistant) -> None:
        async_check_source_issue(hass, entry)

    async_check_source_issue(hass, entry)
    entry.async_on_unload(async_at_started(hass, _when_started))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform(p) for p in PLATFORMS]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
