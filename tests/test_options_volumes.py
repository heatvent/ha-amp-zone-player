"""The startup-volume options page keeps only valid per-zone volumes."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.amp_zone_player.config_flow import AmpZonePlayerOptionsFlow
from custom_components.amp_zone_player.const import (
    CONF_DIGITAL_ZONES,
    CONF_STARTUP_VOLUMES,
    CONF_ZONES,
)

AMP = "media_player.amp_kitchen"
STR = "media_player.theater_str"


def _flow(hass: HomeAssistant, volumes: dict[str, int]) -> tuple[AmpZonePlayerOptionsFlow, list]:
    flow = AmpZonePlayerOptionsFlow()
    flow.hass = hass
    data = {CONF_ZONES: [AMP], CONF_DIGITAL_ZONES: [STR], CONF_STARTUP_VOLUMES: volumes}
    flow._final = (data, "uid")
    saved: list = []
    flow._save = lambda: saved.append(dict(flow._final[0])) or {"type": FlowResultType.CREATE_ENTRY}  # type: ignore[method-assign]
    return flow, saved


async def test_form_lists_every_zone_with_current_volume(hass: HomeAssistant) -> None:
    flow, _saved = _flow(hass, {STR: 30})
    result = await flow.async_step_volumes()
    assert result["type"] is FlowResultType.FORM
    fields = {str(key): key for key in result["data_schema"].schema}
    assert set(fields) == {AMP, STR}
    assert fields[STR].description == {"suggested_value": 30}
    assert fields[AMP].description is None


async def test_blank_zones_are_left_alone(hass: HomeAssistant) -> None:
    flow, saved = _flow(hass, {STR: 30})
    await flow.async_step_volumes({AMP: 22.0})
    assert saved[0][CONF_STARTUP_VOLUMES] == {AMP: 22}
