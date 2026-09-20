"""Config flow for Matrix Amplifier Zone Player."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_DECODER,
    CONF_NAME_PREFIX,
    CONF_SOURCE,
    CONF_ZONES,
    DEFAULT_NAME_PREFIX,
    DOMAIN,
)

SOURCE_NONE = ""
SOURCE_NONE_LABEL = "None — leave zone source as-is"
DEFAULT_ENTRY_TITLE = "Amp zones"


def _entry_title(value: str | None) -> str:
    """Hub/config title. Blank is allowed and becomes a short default."""
    return (value or "").strip() or DEFAULT_ENTRY_TITLE


def _normalize_zones(zones: str | list[str]) -> list[str]:
    if isinstance(zones, str):
        return [zones]
    return list(zones)


def _zone_source_names(hass: HomeAssistant, zones: list[str]) -> list[str]:
    """Plain-text source names from zone media_player.source_list attributes."""
    names: set[str] = set()
    for zone_id in zones:
        state = hass.states.get(zone_id)
        if state is None:
            continue
        for item in state.attributes.get("source_list") or []:
            if isinstance(item, str) and item.strip():
                names.add(item.strip())
    return sorted(names)


def _source_select_schema(
    hass: HomeAssistant, zones: list[str], default: str = SOURCE_NONE
) -> vol.Schema:
    """Dropdown of zone source names; custom_value allows typing an exact name."""
    options: list[selector.SelectOptionDict] = [
        {"value": SOURCE_NONE, "label": SOURCE_NONE_LABEL},
    ]
    for name in _zone_source_names(hass, zones):
        options.append({"value": name, "label": name})

    # Preserve a saved custom name that is not currently in any source_list.
    if default and default not in {opt["value"] for opt in options}:
        options.append({"value": default, "label": f"{default} (saved)"})

    return vol.Schema(
        {
            vol.Optional(CONF_SOURCE, default=default or SOURCE_NONE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                    translation_key="source",
                )
            )
        }
    )


async def _async_validate(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate entities exist and are distinct."""
    errors: dict[str, str] = {}
    decoder = data[CONF_DECODER]
    zones = _normalize_zones(data[CONF_ZONES])

    if hass.states.get(decoder) is None:
        errors[CONF_DECODER] = "entity_not_found"

    if not zones:
        errors[CONF_ZONES] = "no_zones"
    else:
        missing = [z for z in zones if hass.states.get(z) is None]
        if missing:
            errors[CONF_ZONES] = "entity_not_found"
        if decoder in zones:
            errors[CONF_ZONES] = "decoder_in_zones"

    return errors


class AmpZonePlayerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matrix Amplifier Zone Player."""

    VERSION = 1

    def __init__(self) -> None:
        self._partial: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick decoder and amp zones."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_ZONES] = _normalize_zones(user_input[CONF_ZONES])
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                self._partial = {
                    CONF_DECODER: user_input[CONF_DECODER],
                    CONF_ZONES: user_input[CONF_ZONES],
                    CONF_NAME_PREFIX: (
                        user_input.get(CONF_NAME_PREFIX) or DEFAULT_NAME_PREFIX
                    ).strip(),
                    CONF_NAME: _entry_title(user_input.get(CONF_NAME)),
                }
                return await self.async_step_source()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DECODER): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=MP_DOMAIN, multiple=False)
                    ),
                    vol.Required(CONF_ZONES): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=MP_DOMAIN, multiple=True)
                    ),
                    vol.Optional(
                        CONF_NAME_PREFIX, default=DEFAULT_NAME_PREFIX
                    ): selector.TextSelector(),
                    vol.Optional(CONF_NAME, default=""): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick amp input source name (from zone source lists, not an entity)."""
        zones: list[str] = self._partial[CONF_ZONES]

        if user_input is not None:
            source = (user_input.get(CONF_SOURCE) or SOURCE_NONE).strip()
            title = self._partial[CONF_NAME]
            return self.async_create_entry(
                title=title,
                data={
                    CONF_DECODER: self._partial[CONF_DECODER],
                    CONF_ZONES: zones,
                    CONF_SOURCE: source,
                    CONF_NAME_PREFIX: self._partial[CONF_NAME_PREFIX],
                },
            )

        return self.async_show_form(
            step_id="source",
            data_schema=_source_select_schema(self.hass, zones),
            description_placeholders={
                "hint": (
                    "Choose a name from the zone source list (plain text), "
                    "or type the exact label. This is not an entity ID."
                )
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return AmpZonePlayerOptionsFlow()


class AmpZonePlayerOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self) -> None:
        self._partial: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit decoder and zones, then source."""
        errors: dict[str, str] = {}
        data = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            user_input[CONF_ZONES] = _normalize_zones(user_input[CONF_ZONES])
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                self._partial = {
                    CONF_DECODER: user_input[CONF_DECODER],
                    CONF_ZONES: user_input[CONF_ZONES],
                    CONF_NAME_PREFIX: (
                        user_input.get(CONF_NAME_PREFIX) or DEFAULT_NAME_PREFIX
                    ).strip(),
                    CONF_SOURCE: data.get(CONF_SOURCE, SOURCE_NONE),
                }
                return await self.async_step_source()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DECODER, default=data.get(CONF_DECODER)
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=MP_DOMAIN, multiple=False)
                    ),
                    vol.Required(
                        CONF_ZONES, default=data.get(CONF_ZONES, [])
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=MP_DOMAIN, multiple=True)
                    ),
                    vol.Optional(
                        CONF_NAME_PREFIX, default=data.get(CONF_NAME_PREFIX, "")
                    ): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick amp input source name from zone source lists."""
        zones: list[str] = self._partial[CONF_ZONES]
        default = (self._partial.get(CONF_SOURCE) or SOURCE_NONE).strip()

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_DECODER: self._partial[CONF_DECODER],
                    CONF_ZONES: zones,
                    CONF_SOURCE: (user_input.get(CONF_SOURCE) or SOURCE_NONE).strip(),
                    CONF_NAME_PREFIX: self._partial[CONF_NAME_PREFIX],
                },
            )

        return self.async_show_form(
            step_id="source",
            data_schema=_source_select_schema(self.hass, zones, default),
            description_placeholders={
                "hint": (
                    "Choose a name from the zone source list (plain text), "
                    "or type the exact label. This is not an entity ID."
                )
            },
        )
