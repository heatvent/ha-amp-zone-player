"""Facade media players: zone power/volume + decoder transport."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_OFF,
    STATE_ON,
    STATE_PLAYING,
    STATE_PAUSED,
    STATE_IDLE,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_DECODER, CONF_NAME_PREFIX, CONF_SOURCE, CONF_ZONES, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map HA state strings to MediaPlayerState where possible.
_STATE_MAP = {
    STATE_OFF: MediaPlayerState.OFF,
    STATE_ON: MediaPlayerState.ON,
    STATE_PLAYING: MediaPlayerState.PLAYING,
    STATE_PAUSED: MediaPlayerState.PAUSED,
    STATE_IDLE: MediaPlayerState.IDLE,
    STATE_STANDBY: MediaPlayerState.STANDBY,
}


def _merged_config(entry: ConfigEntry) -> dict[str, Any]:
    return {**entry.data, **entry.options}


def _friendly_name(state: State | None, entity_id: str) -> str:
    if state is None:
        return entity_id.split(".", 1)[-1].replace("_", " ").title()
    return state.name or entity_id


def _is_on_state(state: State | None) -> bool:
    if state is None or state.state in (STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN):
        return False
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one facade per configured zone."""
    config = _merged_config(entry)
    decoder = config[CONF_DECODER]
    zones: list[str] = list(config.get(CONF_ZONES) or [])
    source = (config.get(CONF_SOURCE) or "").strip() or None
    prefix = (config.get(CONF_NAME_PREFIX) or "").strip()

    if not zones:
        _LOGGER.error(
            "No zones configured for %s — reconfigure the integration and select amp zone media players",
            entry.title,
        )
        return

    _LOGGER.info(
        "Creating %s Matrix Amplifier Zone Player facade(s) on device '%s' (decoder=%s)",
        len(zones),
        entry.title,
        decoder,
    )

    registry = AmpZoneRegistry(hass, entry.entry_id, zones)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = registry

    async_add_entities(
        [
            AmpZoneFacade(
                hass=hass,
                entry=entry,
                registry=registry,
                zone_entity_id=zone_id,
                decoder_entity_id=decoder,
                source_name=source,
                name_prefix=prefix,
            )
            for zone_id in zones
        ]
    )


class AmpZoneRegistry:
    """Tracks which facade zones are on so off does not stop a shared decoder."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, zone_entity_ids: list[str]
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.zone_entity_ids = list(zone_entity_ids)
        self._on: set[str] = set()

    def mark_on(self, zone_entity_id: str) -> None:
        self._on.add(zone_entity_id)

    def mark_off(self, zone_entity_id: str) -> None:
        self._on.discard(zone_entity_id)

    def any_other_on(self, zone_entity_id: str) -> bool:
        return any(z != zone_entity_id and z in self._on for z in self._on)

    def refresh_from_states(self) -> None:
        self._on = {
            z
            for z in self.zone_entity_ids
            if _is_on_state(self.hass.states.get(z))
        }


class AmpZoneFacade(MediaPlayerEntity):
    """Proxy: amp zone for power/volume, decoder for transport and metadata."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        registry: AmpZoneRegistry,
        zone_entity_id: str,
        decoder_entity_id: str,
        source_name: str | None,
        name_prefix: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._registry = registry
        self._zone_id = zone_entity_id
        self._decoder_id = decoder_entity_id
        self._source_name = source_name
        self._name_prefix = name_prefix
        self._attr_unique_id = f"{entry.entry_id}_{zone_entity_id}"
        base = _friendly_name(hass.states.get(zone_entity_id), zone_entity_id)
        self._attr_name = f"{name_prefix} {base}".strip() if name_prefix else base
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Matrix Amplifier Zone Player",
            "model": "Decoder + zone bridge",
        }

    async def async_added_to_hass(self) -> None:
        self._registry.refresh_from_states()

        @callback
        def _on_change(event: Event) -> None:
            entity_id = event.data.get("entity_id")
            if entity_id == self._zone_id:
                if _is_on_state(self.hass.states.get(self._zone_id)):
                    self._registry.mark_on(self._zone_id)
                else:
                    self._registry.mark_off(self._zone_id)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._zone_id, self._decoder_id], _on_change
            )
        )

    # ----- helpers -----

    def _zone(self) -> State | None:
        return self.hass.states.get(self._zone_id)

    def _decoder(self) -> State | None:
        return self.hass.states.get(self._decoder_id)

    async def _async_call(
        self, service: str, entity_id: str, data: dict[str, Any] | None = None
    ) -> None:
        payload = {ATTR_ENTITY_ID: entity_id, **(data or {})}
        await self.hass.services.async_call(
            MP_DOMAIN, service, payload, blocking=True
        )

    # ----- identity -----

    @property
    def available(self) -> bool:
        zone = self._zone()
        decoder = self._decoder()
        return (
            zone is not None
            and zone.state != STATE_UNAVAILABLE
            and decoder is not None
            and decoder.state != STATE_UNAVAILABLE
        )

    # ----- state & features -----

    @property
    def state(self) -> MediaPlayerState | None:
        zone = self._zone()
        if not _is_on_state(zone):
            return MediaPlayerState.OFF
        decoder = self._decoder()
        if decoder is None:
            return MediaPlayerState.ON
        return _STATE_MAP.get(decoder.state, MediaPlayerState.ON)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )
        decoder = self._decoder()
        if decoder is not None:
            raw = decoder.attributes.get("supported_features")
            if isinstance(raw, int):
                # Keep transport bits the decoder already advertises.
                transport = (
                    MediaPlayerEntityFeature.SEEK
                    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
                    | MediaPlayerEntityFeature.SHUFFLE_SET
                    | MediaPlayerEntityFeature.REPEAT_SET
                    | MediaPlayerEntityFeature.BROWSE_MEDIA
                )
                features |= MediaPlayerEntityFeature(raw) & transport
        return features

    # ----- volume (zone) -----

    @property
    def volume_level(self) -> float | None:
        zone = self._zone()
        if zone is None:
            return None
        return zone.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)

    @property
    def is_volume_muted(self) -> bool | None:
        zone = self._zone()
        if zone is None:
            return None
        return zone.attributes.get(ATTR_MEDIA_VOLUME_MUTED)

    async def async_set_volume_level(self, volume: float) -> None:
        await self._async_call(
            SERVICE_VOLUME_SET, self._zone_id, {ATTR_MEDIA_VOLUME_LEVEL: volume}
        )

    async def async_mute_volume(self, mute: bool) -> None:
        await self._async_call(
            SERVICE_VOLUME_MUTE, self._zone_id, {ATTR_MEDIA_VOLUME_MUTED: mute}
        )

    # ----- power -----

    async def async_turn_on(self) -> None:
        await self._async_call(SERVICE_TURN_ON, self._zone_id)
        if self._source_name:
            await self._async_call(
                "select_source",
                self._zone_id,
                {"source": self._source_name},
            )
        self._registry.mark_on(self._zone_id)

    async def async_turn_off(self) -> None:
        await self._async_call(SERVICE_TURN_OFF, self._zone_id)
        self._registry.mark_off(self._zone_id)
        # Leave decoder running if another facade zone is still on.
        if not self._registry.any_other_on(self._zone_id):
            _LOGGER.debug(
                "Last zone off (%s); leaving decoder %s running for MA",
                self._zone_id,
                self._decoder_id,
            )

    # ----- transport (decoder); ensure zone is on first -----

    async def _async_ensure_zone_on(self) -> None:
        if not _is_on_state(self._zone()):
            await self.async_turn_on()

    async def async_media_play(self) -> None:
        await self._async_ensure_zone_on()
        await self._async_call(SERVICE_MEDIA_PLAY, self._decoder_id)

    async def async_media_pause(self) -> None:
        await self._async_call(SERVICE_MEDIA_PAUSE, self._decoder_id)

    async def async_media_stop(self) -> None:
        # Stop means this room leaves the stream; do not stop shared decoder.
        await self.async_turn_off()

    async def async_media_next_track(self) -> None:
        await self._async_call(SERVICE_MEDIA_NEXT_TRACK, self._decoder_id)

    async def async_media_previous_track(self) -> None:
        await self._async_call(SERVICE_MEDIA_PREVIOUS_TRACK, self._decoder_id)

    async def async_media_seek(self, position: float) -> None:
        await self._async_call(
            SERVICE_MEDIA_SEEK, self._decoder_id, {"seek_position": position}
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        await self._async_ensure_zone_on()
        data: dict[str, Any] = {
            "media_content_type": media_type,
            "media_content_id": media_id,
        }
        for key in (
            "enqueue",
            "announce",
            "extra",
        ):
            if key in kwargs and kwargs[key] is not None:
                data[key] = kwargs[key]
        await self._async_call("play_media", self._decoder_id, data)

    # ----- metadata from decoder -----

    @property
    def media_content_type(self) -> MediaType | str | None:
        decoder = self._decoder()
        if decoder is None:
            return None
        return decoder.attributes.get("media_content_type")

    @property
    def media_content_id(self) -> str | None:
        decoder = self._decoder()
        if decoder is None:
            return None
        return decoder.attributes.get("media_content_id")

    @property
    def media_title(self) -> str | None:
        decoder = self._decoder()
        if decoder is None or not _is_on_state(self._zone()):
            return None
        return decoder.attributes.get("media_title")

    @property
    def media_artist(self) -> str | None:
        decoder = self._decoder()
        if decoder is None or not _is_on_state(self._zone()):
            return None
        return decoder.attributes.get("media_artist")

    @property
    def media_album_name(self) -> str | None:
        decoder = self._decoder()
        if decoder is None or not _is_on_state(self._zone()):
            return None
        return decoder.attributes.get("media_album_name")

    @property
    def media_image_url(self) -> str | None:
        decoder = self._decoder()
        if decoder is None or not _is_on_state(self._zone()):
            return None
        return decoder.attributes.get("entity_picture") or decoder.attributes.get(
            "media_image_url"
        )

    @property
    def media_duration(self) -> int | None:
        decoder = self._decoder()
        if decoder is None:
            return None
        return decoder.attributes.get("media_duration")

    @property
    def media_position(self) -> int | None:
        decoder = self._decoder()
        if decoder is None:
            return None
        return decoder.attributes.get("media_position")

    @property
    def media_position_updated_at(self):
        decoder = self._decoder()
        if decoder is None:
            return None
        return decoder.attributes.get("media_position_updated_at")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "zone_entity_id": self._zone_id,
            "decoder_entity_id": self._decoder_id,
            "on_source": self._source_name,
        }
