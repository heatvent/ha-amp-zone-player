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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DECODER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=MP_DOMAIN, multiple=False)
        ),
        vol.Required(CONF_ZONES): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=MP_DOMAIN, multiple=True)
        ),
        vol.Optional(CONF_SOURCE, default=""): selector.TextSelector(),
        vol.Optional(CONF_NAME_PREFIX, default=DEFAULT_NAME_PREFIX): selector.TextSelector(),
        vol.Optional(CONF_NAME, default="Matrix amp zones"): selector.TextSelector(),
    }
)


def _normalize_zones(zones: str | list[str]) -> list[str]:
    if isinstance(zones, str):
        return [zones]
    return list(zones)


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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_ZONES] = _normalize_zones(user_input[CONF_ZONES])
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                title = user_input.get(CONF_NAME) or "Matrix Amplifier Zone Player"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_DECODER: user_input[CONF_DECODER],
                        CONF_ZONES: user_input[CONF_ZONES],
                        CONF_SOURCE: (user_input.get(CONF_SOURCE) or "").strip(),
                        CONF_NAME_PREFIX: (
                            user_input.get(CONF_NAME_PREFIX) or DEFAULT_NAME_PREFIX
                        ).strip(),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return AmpZonePlayerOptionsFlow()


class AmpZonePlayerOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options (same fields as setup)."""
        errors: dict[str, str] = {}
        data = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            user_input[CONF_ZONES] = _normalize_zones(user_input[CONF_ZONES])
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_DECODER: user_input[CONF_DECODER],
                        CONF_ZONES: user_input[CONF_ZONES],
                        CONF_SOURCE: (user_input.get(CONF_SOURCE) or "").strip(),
                        CONF_NAME_PREFIX: (
                            user_input.get(CONF_NAME_PREFIX) or DEFAULT_NAME_PREFIX
                        ).strip(),
                    },
                )

        schema = vol.Schema(
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
                    CONF_SOURCE, default=data.get(CONF_SOURCE, "")
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_NAME_PREFIX, default=data.get(CONF_NAME_PREFIX, "")
                ): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
