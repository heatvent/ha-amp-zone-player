"""Repair flows for Music Assistant Amp Zone Player."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import CONF_SOURCE, CONF_ZONES, DOMAIN
from .helpers import normalize_source


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow for the given issue."""
    if issue_id.startswith("bad_source_"):
        return BadSourceRepairFlow()
    raise ValueError(f"Unknown repair issue_id: {issue_id}")


class BadSourceRepairFlow(RepairsFlow):
    """Clear a configured amp source that is missing from zone source lists."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        if user_input is not None:
            entry_id = (self.data or {}).get("entry_id")
            entry = (
                self.hass.config_entries.async_get_entry(str(entry_id))
                if entry_id
                else None
            )
            if entry is not None:
                new_data = {**entry.data, CONF_SOURCE: ""}
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return self.async_create_entry(data={})

        source = str((self.data or {}).get("source") or "")
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"source": source},
        )


@callback
def async_check_source_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create or clear a repair if configured source is missing from zones."""
    issue_id = f"bad_source_{entry.entry_id}"
    source = normalize_source(entry.data.get(CONF_SOURCE))
    zones = list(entry.data.get(CONF_ZONES) or [])

    if not source or not zones:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    names: set[str] = set()
    any_list = False
    for zone_id in zones:
        state = hass.states.get(zone_id)
        if state is None:
            continue
        raw = state.attributes.get("source_list") or []
        if not isinstance(raw, list):
            continue
        any_list = True
        for item in raw:
            if isinstance(item, str) and item.strip():
                names.add(item.strip())

    if not any_list or source in names:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="bad_source",
        translation_placeholders={"source": source, "title": entry.title or DOMAIN},
        data={"entry_id": entry.entry_id, "source": source},
    )
