"""Config flow for Music Assistant Amp Zone Player."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_DECODER,
    CONF_NAME_PREFIX,
    CONF_SOURCE,
    CONF_ZONES,
    DEFAULT_NAME_PREFIX,
    DOMAIN,
)

SOURCE_NONE = "__none__"
SOURCE_NONE_LABEL = "None — leave zone source as-is"
DEFAULT_ENTRY_TITLE = "Amp zones"

# Amp zones come from Control4 Audio (one media_player per speaker zone).
_ZONE_INTEGRATIONS = frozenset({"c4_audio"})

# Real streamers / decoders — not amp zones, MA facades, or Alexa.
_DECODER_INTEGRATIONS = frozenset(
    {
        "wiim",
        "linkplay",
        "dlna_dmr",
        "cast",
        "bluesound",
        "heos",
        "squeezebox",
        "sonos",
    }
)


def _entry_title(value: str | None) -> str:
    """Hub/config title. Blank is allowed and becomes a short default."""
    return (value or "").strip() or DEFAULT_ENTRY_TITLE


def _normalize_zones(zones: str | list[str]) -> list[str]:
    if isinstance(zones, str):
        return [zones]
    return list(zones)


def _normalize_source(value: str | None) -> str:
    """Stored source name; blank means leave zone source as-is."""
    raw = (value or "").strip()
    if not raw or raw == SOURCE_NONE:
        return ""
    return raw


def _source_form_value(stored: str | None) -> str:
    """Select option value for a previously saved source."""
    raw = (stored or "").strip()
    return raw if raw else SOURCE_NONE


def _entry_unique_id(decoder: str, zones: list[str]) -> str:
    return f"{decoder}|{'|'.join(sorted(zones))}"


def _is_amp_speaker_zone(entry: er.RegistryEntry) -> bool:
    """True for room speaker zones; false for bare amp/switch media_players."""
    if entry.domain != MP_DOMAIN or entry.platform not in _ZONE_INTEGRATIONS:
        return False
    if entry.disabled_by is not None:
        return False
    object_id = entry.entity_id.partition(".")[2]
    # Control4 Switch matrix endpoints are not room zones.
    if object_id.startswith("control4_switch_"):
        return False
    label = (entry.name or entry.original_name or object_id).lower()
    return "speaker" in label


def _amp_speaker_zone_ids(hass: HomeAssistant) -> list[str]:
    registry = er.async_get(hass)
    return sorted(
        entry.entity_id
        for entry in registry.entities.values()
        if _is_amp_speaker_zone(entry)
    )


def _media_player_selector(
    *,
    multiple: bool,
    integrations: frozenset[str],
    include_entities: list[str] | None = None,
) -> selector.EntitySelector:
    """Entity picker limited to media_players from the given integrations."""
    config: dict[str, Any] = {
        "multiple": multiple,
        "filter": [
            {
                "domain": MP_DOMAIN,
                "integration": integration,
            }
            for integration in sorted(integrations)
        ],
    }
    # Empty allow-list would hide everything; fall back to integration filter.
    if include_entities:
        config["include_entities"] = include_entities
    return selector.EntitySelector(selector.EntitySelectorConfig(**config))


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
    form_default = _source_form_value(default)
    options: list[selector.SelectOptionDict] = [
        {"value": SOURCE_NONE, "label": SOURCE_NONE_LABEL},
    ]
    for name in _zone_source_names(hass, zones):
        options.append({"value": name, "label": name})

    # Preserve a saved custom name that is not currently in any source_list.
    if form_default != SOURCE_NONE and form_default not in {
        opt["value"] for opt in options
    }:
        options.append({"value": form_default, "label": f"{form_default} (saved)"})

    return vol.Schema(
        {
            vol.Optional(CONF_SOURCE, default=form_default): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            )
        }
    )


def _platform_for(hass: HomeAssistant, entity_id: str) -> str | None:
    entry = er.async_get(hass).async_get(entity_id)
    return entry.platform if entry else None


async def _async_validate(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate entities exist, are distinct, and match expected integrations."""
    errors: dict[str, str] = {}
    decoder = data[CONF_DECODER]
    zones = _normalize_zones(data[CONF_ZONES])

    if hass.states.get(decoder) is None:
        errors[CONF_DECODER] = "entity_not_found"
    elif _platform_for(hass, decoder) not in _DECODER_INTEGRATIONS:
        errors[CONF_DECODER] = "bad_decoder"

    if not zones:
        errors[CONF_ZONES] = "no_zones"
    else:
        missing = [z for z in zones if hass.states.get(z) is None]
        if missing:
            errors[CONF_ZONES] = "entity_not_found"
        elif decoder in zones:
            errors[CONF_ZONES] = "decoder_in_zones"
        elif any(
            (reg := er.async_get(hass).async_get(z)) is None
            or not _is_amp_speaker_zone(reg)
            for z in zones
        ):
            errors[CONF_ZONES] = "bad_zone"

    return errors


def _user_schema(hass: HomeAssistant) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_DECODER): _media_player_selector(
                multiple=False, integrations=_DECODER_INTEGRATIONS
            ),
            vol.Required(CONF_ZONES): _media_player_selector(
                multiple=True,
                integrations=_ZONE_INTEGRATIONS,
                include_entities=_amp_speaker_zone_ids(hass),
            ),
            vol.Optional(
                CONF_NAME_PREFIX, default=DEFAULT_NAME_PREFIX
            ): selector.TextSelector(),
            vol.Optional(CONF_NAME, default=""): selector.TextSelector(),
        }
    )


def _options_schema(hass: HomeAssistant, data: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DECODER, default=data.get(CONF_DECODER)
            ): _media_player_selector(
                multiple=False, integrations=_DECODER_INTEGRATIONS
            ),
            vol.Required(
                CONF_ZONES, default=data.get(CONF_ZONES, [])
            ): _media_player_selector(
                multiple=True,
                integrations=_ZONE_INTEGRATIONS,
                include_entities=_amp_speaker_zone_ids(hass),
            ),
            vol.Optional(
                CONF_NAME_PREFIX, default=data.get(CONF_NAME_PREFIX, "")
            ): selector.TextSelector(),
        }
    )


class AmpZonePlayerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Music Assistant Amp Zone Player."""

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
                zones = user_input[CONF_ZONES]
                decoder = user_input[CONF_DECODER]
                await self.async_set_unique_id(_entry_unique_id(decoder, zones))
                self._abort_if_unique_id_configured()
                self._partial = {
                    CONF_DECODER: decoder,
                    CONF_ZONES: zones,
                    CONF_NAME_PREFIX: (
                        user_input.get(CONF_NAME_PREFIX) or DEFAULT_NAME_PREFIX
                    ).strip(),
                    CONF_NAME: _entry_title(user_input.get(CONF_NAME)),
                }
                return await self.async_step_source()

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self.hass),
            errors=errors,
        )

    async def async_step_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick amp input source name (from zone source lists, not an entity)."""
        zones: list[str] = self._partial[CONF_ZONES]

        if user_input is not None:
            source = _normalize_source(user_input.get(CONF_SOURCE))
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
                decoder = user_input[CONF_DECODER]
                zones = user_input[CONF_ZONES]
                new_uid = _entry_unique_id(decoder, zones)
                for other in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        other.entry_id != self.config_entry.entry_id
                        and other.unique_id == new_uid
                    ):
                        errors["base"] = "already_configured"
                        break
                if not errors:
                    self._partial = {
                        CONF_DECODER: decoder,
                        CONF_ZONES: zones,
                        CONF_NAME_PREFIX: (
                            user_input.get(CONF_NAME_PREFIX) or DEFAULT_NAME_PREFIX
                        ).strip(),
                        CONF_SOURCE: data.get(CONF_SOURCE, ""),
                        "unique_id": new_uid,
                    }
                    return await self.async_step_source()

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.hass, data),
            errors=errors,
        )

    async def async_step_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick amp input source name from zone source lists."""
        zones: list[str] = self._partial[CONF_ZONES]
        default = self._partial.get(CONF_SOURCE, "")

        if user_input is not None:
            new_data = {
                CONF_DECODER: self._partial[CONF_DECODER],
                CONF_ZONES: zones,
                CONF_SOURCE: _normalize_source(user_input.get(CONF_SOURCE)),
                CONF_NAME_PREFIX: self._partial[CONF_NAME_PREFIX],
            }
            # Keep config in entry.data (not options) and refresh unique_id.
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
                options={},
                unique_id=self._partial["unique_id"],
            )
            return self.async_create_entry(data={})

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
