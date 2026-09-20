"""Facade media players: Composer-style session (leader + joinable zones)."""

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_DECODER, CONF_NAME_PREFIX, CONF_SOURCE, CONF_ZONES, DOMAIN
from .naming import facade_name, facade_object_id
from .session import AmpSession

_LOGGER = logging.getLogger(__name__)

DEVICE_NAME_FALLBACK = "Amp zones"

_STATE_MAP = {
    STATE_OFF: MediaPlayerState.OFF,
    STATE_ON: MediaPlayerState.ON,
    STATE_PLAYING: MediaPlayerState.PLAYING,
    STATE_PAUSED: MediaPlayerState.PAUSED,
    STATE_IDLE: MediaPlayerState.IDLE,
    STATE_STANDBY: MediaPlayerState.STANDBY,
}

# Only advertise transport bits we actually implement as passthrough.
_PASSTHROUGH_FEATURES = MediaPlayerEntityFeature.SEEK


def _merged_config(entry: ConfigEntry) -> dict[str, Any]:
    return {**entry.data, **entry.options}


def _is_on_state(state: State | None) -> bool:
    if state is None or state.state in (STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN):
        return False
    return True


def _short_media_id(media_id: str, limit: int = 80) -> str:
    if len(media_id) <= limit:
        return media_id
    return media_id[:limit] + "…"


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
            "No zones configured for %s — reconfigure and select amp zone media players",
            entry.title,
        )
        return

    if not decoder:
        _LOGGER.error("No decoder configured for %s", entry.title)
        return

    session = AmpSession(hass, entry.entry_id)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = session

    _LOGGER.info(
        "Creating %s zone facade(s) with Composer-style grouping (decoder=%s)",
        len(zones),
        decoder,
    )

    async_add_entities(
        [
            AmpZoneFacade(
                hass=hass,
                entry=entry,
                session=session,
                zone_entity_id=zone_id,
                decoder_entity_id=decoder,
                source_name=source,
                name_prefix=prefix,
            )
            for zone_id in zones
        ]
    )


class AmpZoneFacade(MediaPlayerEntity):
    """
    Zone facade for Music Assistant / HA.

    Play/queue goes to the shared decoder (WiiM). Zones join/unjoin the session
    like Control4 Composer rooms — HA GROUPING so MA can add rooms and show
    per-member volume.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: AmpSession,
        zone_entity_id: str,
        decoder_entity_id: str,
        source_name: str | None,
        name_prefix: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._session = session
        self._zone_id = zone_entity_id
        self._decoder_id = decoder_entity_id
        self._source_name = source_name
        self._name_prefix = name_prefix
        self._attr_unique_id = f"{entry.entry_id}_{zone_entity_id}"
        short = facade_name(hass, zone_entity_id, name_prefix)
        self._attr_name = short
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": (entry.title or "").strip() or DEVICE_NAME_FALLBACK,
            "manufacturer": "Music Assistant Amp Zone Player",
            "model": "Decoder + zone bridge",
        }

    @property
    def zone_entity_id(self) -> str:
        return self._zone_id

    async def async_added_to_hass(self) -> None:
        self._async_force_short_identity()
        self._session.register(self)
        self.async_on_remove(lambda: self._session.unregister(self))
        self.async_on_remove(
            self._session.async_add_listener(self._handle_session_update)
        )

        @callback
        def _on_change(_event: Event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._zone_id, self._decoder_id], _on_change
            )
        )

    @callback
    def _handle_session_update(self) -> None:
        self.async_write_ha_state()

    @callback
    def _async_force_short_identity(self) -> None:
        if not self.entity_id:
            return
        short = facade_name(self.hass, self._zone_id, self._name_prefix)
        self._attr_name = short
        registry = er.async_get(self.hass)
        entry = registry.async_get(self.entity_id)
        if entry is None:
            return
        updates: dict[str, Any] = {
            "has_entity_name": False,
            "name": short,
            "original_name": short,
        }
        desired = f"media_player.{facade_object_id(short)}"
        if self.entity_id != desired:
            conflict = registry.async_get(desired)
            if conflict is None or conflict.unique_id == entry.unique_id:
                updates["new_entity_id"] = desired
        registry.async_update_entity(self.entity_id, **updates)

    def _zone(self) -> State | None:
        return self.hass.states.get(self._zone_id)

    def _decoder(self) -> State | None:
        return self.hass.states.get(self._decoder_id)

    async def _async_call(
        self,
        service: str,
        entity_id: str,
        data: dict[str, Any] | None = None,
        *,
        critical: bool = True,
    ) -> bool:
        """Call a media_player service. Returns False on soft failure."""
        payload = {ATTR_ENTITY_ID: entity_id, **(data or {})}
        try:
            await self.hass.services.async_call(
                MP_DOMAIN, service, payload, blocking=True
            )
            return True
        except HomeAssistantError as err:
            _LOGGER.warning(
                "%s.%s on %s failed: %s",
                MP_DOMAIN,
                service,
                entity_id,
                err,
            )
            if critical:
                raise
            return False
        except Exception:
            _LOGGER.exception(
                "%s.%s on %s raised unexpectedly", MP_DOMAIN, service, entity_id
            )
            if critical:
                raise
            return False

    async def async_power_zone_on(self) -> None:
        """Turn the underlying amp zone on (and select decoder source)."""
        await self._async_call(SERVICE_TURN_ON, self._zone_id, critical=True)
        if self._source_name:
            # Wrong/missing source name must not abort join/play.
            ok = await self._async_call(
                "select_source",
                self._zone_id,
                {"source": self._source_name},
                critical=False,
            )
            if not ok:
                _LOGGER.warning(
                    "Could not select source %r on %s — check amp source_list spelling",
                    self._source_name,
                    self._zone_id,
                )

    async def async_power_zone_off(self) -> None:
        """Turn the underlying amp zone off."""
        await self._async_call(SERVICE_TURN_OFF, self._zone_id, critical=False)

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

    @property
    def group_members(self) -> list[str]:
        if not self.entity_id:
            return []
        return self._session.group_members_for(self.entity_id)

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
            | MediaPlayerEntityFeature.GROUPING
        )
        decoder = self._decoder()
        if decoder is not None:
            raw = decoder.attributes.get("supported_features")
            if isinstance(raw, int):
                features |= MediaPlayerEntityFeature(raw) & _PASSTHROUGH_FEATURES
        return features

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

    async def async_join_players(self, group_members: list[str]) -> None:
        """Add rooms to this session (this player is the leader)."""
        if not self.entity_id:
            return
        await self._session.async_join(self.entity_id, list(group_members or []))

    async def async_unjoin_player(self) -> None:
        """Leave the session — zone off (Composer: remove room)."""
        if not self.entity_id:
            return
        await self._session.async_unjoin(self.entity_id)

    async def async_turn_on(self) -> None:
        """Power zone on; join existing session or start a solo session."""
        if not self.entity_id:
            return
        await self.async_power_zone_on()
        if self._session.leader_id and self._session.leader_id != self.entity_id:
            await self._session.async_join(
                self._session.leader_id, [self.entity_id]
            )
        else:
            await self._session.async_ensure_leader(self.entity_id)

    async def async_turn_off(self) -> None:
        """Leave session / power zone off."""
        await self.async_unjoin_player()

    async def async_media_play(self) -> None:
        if self.entity_id:
            await self._session.async_ensure_leader(self.entity_id)
        await self._async_call(SERVICE_MEDIA_PLAY, self._decoder_id)

    async def async_media_pause(self) -> None:
        await self._async_call(SERVICE_MEDIA_PAUSE, self._decoder_id)

    async def async_media_stop(self) -> None:
        """Stop the shared decoder stream (MA calls this before/after play).

        Leaving a room is turn_off / unjoin — not media_stop.
        """
        stopped = await self._async_call(
            SERVICE_MEDIA_STOP, self._decoder_id, critical=False
        )
        if not stopped:
            # Some streamers (incl. older LinkPlay) reject stop — pause is enough.
            await self._async_call(
                SERVICE_MEDIA_PAUSE, self._decoder_id, critical=False
            )

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
        """Start/queue on decoder; this facade becomes session leader."""
        if not media_id:
            raise HomeAssistantError("play_media requires a media_content_id")

        if self.entity_id:
            await self._session.async_ensure_leader(self.entity_id)

        # Wake the streamer — some WiiM/LinkPlay entities ignore play_media while off.
        await self._async_call(
            SERVICE_TURN_ON, self._decoder_id, critical=False
        )

        # Music Assistant HA players always send an HTTP URL with type "music".
        # Do not forward Cast-style `extra` / enqueue — many streamers reject them.
        content_type: MediaType | str = media_type or MediaType.MUSIC
        if isinstance(media_id, str) and media_id.startswith(("http://", "https://")):
            content_type = MediaType.MUSIC

        data: dict[str, Any] = {
            "media_content_type": content_type,
            "media_content_id": media_id,
        }
        _LOGGER.info(
            "play_media → decoder %s type=%s id=%s",
            self._decoder_id,
            content_type,
            _short_media_id(str(media_id)),
        )
        try:
            await self._async_call("play_media", self._decoder_id, data, critical=True)
        except Exception:
            _LOGGER.exception(
                "play_media failed on decoder %s — confirm the entity can play URLs "
                "(HA Media Players → HTTP Profile on the facade may also help)",
                self._decoder_id,
            )
            raise

    def _decoder_attr(self, key: str) -> Any:
        decoder = self._decoder()
        if decoder is None:
            return None
        return decoder.attributes.get(key)

    def _session_media_attr(self, key: str) -> Any:
        """Media metadata only when this zone is on (hearing the feed)."""
        if not _is_on_state(self._zone()):
            return None
        return self._decoder_attr(key)

    @property
    def media_content_type(self) -> MediaType | str | None:
        return self._decoder_attr("media_content_type")

    @property
    def media_content_id(self) -> str | None:
        return self._decoder_attr("media_content_id")

    @property
    def media_title(self) -> str | None:
        return self._session_media_attr("media_title")

    @property
    def media_artist(self) -> str | None:
        return self._session_media_attr("media_artist")

    @property
    def media_album_name(self) -> str | None:
        return self._session_media_attr("media_album_name")

    @property
    def media_image_url(self) -> str | None:
        if not _is_on_state(self._zone()):
            return None
        decoder = self._decoder()
        if decoder is None:
            return None
        return decoder.attributes.get("entity_picture") or decoder.attributes.get(
            "media_image_url"
        )

    @property
    def media_duration(self) -> int | None:
        return self._decoder_attr("media_duration")

    @property
    def media_position(self) -> int | None:
        return self._decoder_attr("media_position")

    @property
    def media_position_updated_at(self):
        return self._decoder_attr("media_position_updated_at")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "zone_entity_id": self._zone_id,
            "decoder_entity_id": self._decoder_id,
            "on_source": self._source_name,
            "session_leader": self._session.leader_id,
            "session_members": self._session.members,
        }
