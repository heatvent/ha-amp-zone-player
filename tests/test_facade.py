"""Facade power-on sends only the commands a zone still needs; areas follow rooms."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.amp_zone_player.const import DOMAIN, ZONE_KIND_AMP, ZONE_KIND_DIGITAL
from custom_components.amp_zone_player.media_player import AmpZoneFacade
from custom_components.amp_zone_player.session import AmpSession

DECODER = "media_player.wiim_ma_decoder"
AMP_ZONE = "media_player.amp_kitchen"
STR_ZONE = "media_player.theater_str"
RECEIVER = "media_player.theater_receiver"


def _facade(
    hass: HomeAssistant,
    kind: str,
    zone: str,
    *,
    sound_mode: str | None = None,
    volume: float | None = None,
) -> tuple[AmpZoneFacade, list[tuple[str, str, dict[str, Any]]]]:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    facade = AmpZoneFacade(
        hass=hass,
        entry=entry,
        session=AmpSession(hass, entry.entry_id),
        zone_entity_id=zone,
        decoder_entity_id=DECODER,
        playback_entity_id=None,
        source_name="WiiM Pro" if kind == ZONE_KIND_AMP else None,
        name_prefix="",
        zone_kind=kind,
        digital_sound_mode=sound_mode,
        startup_volume=volume,
    )
    facade.entity_id = "media_player.test_facade"
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _record(service, entity_id, data=None, *, critical=True):
        calls.append((service, entity_id, data or {}))
        if service == "turn_on" and entity_id == AMP_ZONE:
            # What the Control4 zone does on turn_on: route the WiiM input, unmuted.
            hass.states.async_set(AMP_ZONE, "on", {"source": "WiiM Pro", "is_volume_muted": False})
        return True

    facade._async_call = _record  # type: ignore[method-assign]
    return facade, calls


async def test_amp_zone_off_needs_only_turn_on(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "off", {})
    facade, calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE)
    assert await facade.async_power_zone_on()
    assert [c[0] for c in calls] == ["turn_on"]


async def test_amp_zone_already_playing_sends_nothing(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", {"source": "WiiM Pro", "is_volume_muted": False})
    facade, calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE)
    assert await facade.async_power_zone_on()
    assert calls == []


async def test_amp_zone_on_other_input_and_muted(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", {"source": "Turntable", "is_volume_muted": True})
    facade, calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE)
    assert await facade.async_power_zone_on()
    assert [(c[0], c[2]) for c in calls] == [
        ("select_source", {"source": "WiiM Pro"}),
        ("volume_mute", {"is_volume_muted": False}),
    ]


async def test_digital_zone_already_in_sync_group_sends_nothing(hass: HomeAssistant) -> None:
    hass.states.async_set(DECODER, "playing", {"group_members": [DECODER, STR_ZONE]})
    hass.states.async_set(STR_ZONE, "playing", {"group_members": [DECODER, STR_ZONE]})
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, sound_mode="Multi Stereo")
    assert await facade.async_power_zone_on()
    assert calls == []


async def test_digital_join_applies_mode_on_receiver(hass: HomeAssistant) -> None:
    hass.states.async_set(DECODER, "idle", {"group_members": []})
    hass.states.async_set(STR_ZONE, "idle", {})
    hass.states.async_set(RECEIVER, "on", {"sound_mode_list": ["2ch Stereo", "Multi Stereo"]})
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, sound_mode="Multi Stereo")
    assert await facade.async_power_zone_on()
    assert [(c[0], c[1]) for c in calls] == [
        ("turn_on", STR_ZONE),
        ("select_sound_mode", RECEIVER),
        ("join", DECODER),
    ]
    facade._cancel_background_tasks()


async def test_digital_join_skips_unsupported_mode(hass: HomeAssistant) -> None:
    hass.states.async_set(DECODER, "idle", {"group_members": []})
    hass.states.async_set(STR_ZONE, "idle", {})
    hass.states.async_set(RECEIVER, "on", {"sound_mode_list": ["2ch Stereo", "Direct"]})
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, sound_mode="Multi Stereo")
    assert await facade.async_power_zone_on()
    assert [c[0] for c in calls] == ["turn_on", "join"]
    facade._cancel_background_tasks()


async def test_amp_zone_powered_on_starts_at_its_volume(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "off", {})
    facade, calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE, volume=0.25)
    assert await facade.async_power_zone_on()
    assert [(c[0], c[2]) for c in calls] == [
        ("turn_on", {}),
        ("volume_set", {"volume_level": 0.25}),
    ]


async def test_amp_zone_already_on_keeps_its_volume(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", {"source": "WiiM Pro", "is_volume_muted": False})
    facade, calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE, volume=0.25)
    assert await facade.async_power_zone_on()
    assert calls == []


async def test_digital_join_sets_startup_volume(hass: HomeAssistant) -> None:
    hass.states.async_set(DECODER, "idle", {"group_members": []})
    hass.states.async_set(STR_ZONE, "idle", {})
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, volume=0.3)
    assert await facade.async_power_zone_on()
    assert [(c[0], c[1]) for c in calls] == [
        ("turn_on", STR_ZONE),
        ("join", DECODER),
        ("volume_set", STR_ZONE),
    ]
    facade._cancel_background_tasks()


async def test_digital_already_synced_keeps_its_volume(hass: HomeAssistant) -> None:
    hass.states.async_set(DECODER, "playing", {"group_members": [DECODER, STR_ZONE]})
    hass.states.async_set(STR_ZONE, "playing", {"group_members": [DECODER, STR_ZONE]})
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, volume=0.3)
    assert await facade.async_power_zone_on()
    assert calls == []


@pytest.mark.parametrize(
    ("kind", "zone", "room_entity", "expected"),
    [
        (ZONE_KIND_AMP, AMP_ZONE, AMP_ZONE, "Kitchen"),
        (ZONE_KIND_DIGITAL, STR_ZONE, RECEIVER, "Theater"),
    ],
)
async def test_facade_adopts_room_area(
    hass: HomeAssistant, kind: str, zone: str, room_entity: str, expected: str
) -> None:
    areas = ar.async_get(hass)
    room = areas.async_create(expected)
    closet = areas.async_create("Media Closet")
    entities = er.async_get(hass)
    entities.async_get_or_create("media_player", "test", room_entity, suggested_object_id=room_entity.split(".")[1])
    entities.async_update_entity(room_entity, area_id=room.id)
    if zone != room_entity:
        # The MA proxy lives in the closet; a digital facade must not copy that.
        entities.async_get_or_create("media_player", "test", zone, suggested_object_id=zone.split(".")[1])
        entities.async_update_entity(zone, area_id=closet.id)
    facade, _calls = _facade(hass, kind, zone)
    own = entities.async_get_or_create("media_player", DOMAIN, "facade", suggested_object_id="test_facade")
    facade.entity_id = own.entity_id

    facade._adopt_room_area()
    assert entities.async_get(own.entity_id).area_id == room.id

    # A user-chosen area is never overridden.
    entities.async_update_entity(own.entity_id, area_id=closet.id)
    facade._adopt_room_area()
    assert entities.async_get(own.entity_id).area_id == closet.id
