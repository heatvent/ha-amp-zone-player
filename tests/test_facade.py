"""Facade power-on sends only the commands a zone still needs; areas follow rooms."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
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
    power_off: bool = False,
    off_mode: str | None = None,
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
        power_off=power_off,
        off_sound_mode=off_mode,
    )
    facade.entity_id = "media_player.test_facade"
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _record(service, entity_id, data=None, *, critical=True):
        calls.append((service, entity_id, data or {}))
        if service == "turn_on" and entity_id == AMP_ZONE:
            # What the Control4 zone does on turn_on: route the WiiM input, unmuted.
            hass.states.async_set(AMP_ZONE, "on", {"source": "WiiM Pro", "is_volume_muted": False})
        elif service == "turn_off" and entity_id == RECEIVER:
            state = hass.states.get(RECEIVER)
            hass.states.async_set(RECEIVER, "off", dict(state.attributes) if state else {})
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


MUTED = {"source": "WiiM Pro", "is_volume_muted": True}
UNMUTE = ("volume_mute", {"is_volume_muted": False})


def _session_of_two(hass: HomeAssistant):
    """A leader facade and a second one in the same session, both amp zones."""
    leader, leader_calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE)
    other, other_calls = _facade(hass, ZONE_KIND_AMP, "media_player.amp_bar")
    other.entity_id = "media_player.other_facade"
    session = leader._session
    other._session = session
    session._facades = {leader.entity_id: leader, other.entity_id: other}
    return session, leader, leader_calls, other, other_calls


async def test_adding_a_room_keeps_the_leader_muted(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", MUTED)
    hass.states.async_set("media_player.amp_bar", "on", MUTED)
    session, leader, calls, other, other_calls = _session_of_two(hass)
    session._members, session.leader_id = [leader.entity_id], leader.entity_id
    await session.async_join(leader.entity_id, [other.entity_id])
    assert session.members == [leader.entity_id, other.entity_id]
    assert calls == []
    # The room that joins is still unmuted.
    assert [(c[0], c[2]) for c in other_calls] == [UNMUTE]


async def test_member_taking_over_as_leader_keeps_its_mute(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", MUTED)
    hass.states.async_set("media_player.amp_bar", "on", MUTED)
    session, leader, calls, other, other_calls = _session_of_two(hass)
    session._members = [leader.entity_id, other.entity_id]
    session.leader_id = leader.entity_id
    await session.async_join(other.entity_id, [leader.entity_id])
    assert session.leader_id == other.entity_id
    assert calls == other_calls == []


async def test_leader_new_to_the_session_is_unmuted(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", MUTED)
    hass.states.async_set("media_player.amp_bar", "on", MUTED)
    session, leader, calls, other, _ = _session_of_two(hass)
    await session.async_join(leader.entity_id, [other.entity_id])
    assert [(c[0], c[2]) for c in calls] == [UNMUTE]


async def test_play_unmutes_the_room(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", MUTED)
    session, leader, calls, _, _ = _session_of_two(hass)
    session._members, session.leader_id = [leader.entity_id], leader.entity_id
    await session.async_ensure_leader(leader.entity_id)
    assert [(c[0], c[2]) for c in calls] == [UNMUTE]


URL = "http://ma.local/flow.mp3"


def _muted_member(hass: HomeAssistant):
    hass.states.async_set(AMP_ZONE, "on", MUTED)
    session, leader, calls, _, _ = _session_of_two(hass)
    session._members, session.leader_id = [leader.entity_id], leader.entity_id
    async_track_state_change_event(hass, [DECODER], leader._note_feed_change)
    return leader, calls


async def _feed(hass: HomeAssistant, *states: str) -> None:
    for state in states:
        hass.states.async_set(DECODER, state, {})
        await hass.async_block_till_done()


@pytest.mark.parametrize("feed", [["playing"], ["playing", "idle"]], ids=["next", "stopped first"])
async def test_next_and_seek_keep_the_room_muted(hass: HomeAssistant, feed) -> None:
    leader, calls = _muted_member(hass)
    await _feed(hass, *feed)
    await leader.async_play_media("music", URL)
    assert UNMUTE not in [(c[0], c[2]) for c in calls]
    assert "play_media" in [c[0] for c in calls]


@pytest.mark.parametrize(
    "feed",
    [["idle"], ["paused"], ["playing", "paused"], ["playing", "paused", "idle"], ["playing", "idle", "playing", "paused"]],
)
async def test_playing_after_a_pause_unmutes_the_room(hass: HomeAssistant, feed) -> None:
    leader, calls = _muted_member(hass)
    await _feed(hass, *feed)
    await leader.async_play_media("music", URL)
    assert UNMUTE in [(c[0], c[2]) for c in calls]


async def test_playing_a_while_after_a_stop_unmutes_the_room(hass: HomeAssistant) -> None:
    leader, calls = _muted_member(hass)
    await _feed(hass, "playing", "idle")
    leader._feed_stopped_at -= 6
    await leader.async_play_media("music", URL)
    assert UNMUTE in [(c[0], c[2]) for c in calls]


async def test_resume_unmutes_the_room(hass: HomeAssistant) -> None:
    leader, calls = _muted_member(hass)
    await _feed(hass, "playing", "paused")
    await leader.async_media_play()
    assert [(c[0], c[2]) for c in calls] == [UNMUTE, ("media_play", {})]


async def test_room_new_to_the_music_is_unmuted_while_it_plays(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "on", MUTED)
    _, leader, calls, _, _ = _session_of_two(hass)
    await _feed(hass, "playing")
    await leader.async_play_media("music", URL)
    assert UNMUTE in [(c[0], c[2]) for c in calls]


async def test_leader_that_was_off_is_unmuted(hass: HomeAssistant) -> None:
    """Amps that stay muted through turn_on need the unmute, member or not."""
    hass.states.async_set(AMP_ZONE, "off", {})
    facade, calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE)

    async def _muted_turn_on(service, entity_id, data=None, *, critical=True):
        calls.append((service, entity_id, data or {}))
        if service == "turn_on":
            hass.states.async_set(AMP_ZONE, "on", MUTED)
        return True

    facade._async_call = _muted_turn_on  # type: ignore[method-assign]
    assert await facade.async_power_zone_on(keep_mute=True)
    assert [(c[0], c[2]) for c in calls] == [("turn_on", {}), UNMUTE]


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


AFD = "Auto Format Decoding for Movie"


def _receiver(hass: HomeAssistant, source: str | None) -> None:
    attrs = {"sound_mode_list": ["Multi Stereo", AFD]}
    if source is not None:
        attrs["source"] = source
    hass.states.async_set(RECEIVER, "on", attrs)


async def _turn_off_after_music(hass, facade, joined: str | None, now: str | None):
    hass.states.async_set(STR_ZONE, "idle", {})
    _receiver(hass, joined)
    facade._remember_receiver_source()
    facade._digital_seen_in_sync = True
    _receiver(hass, now)
    await facade.async_power_zone_off()


async def test_room_off_turns_its_receiver_off_in_movie_mode(hass: HomeAssistant) -> None:
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, power_off=True, off_mode=AFD)
    # Sony keeps reporting the last HDMI input while it plays AirPlay.
    await _turn_off_after_music(hass, facade, "FIRE TV", "FIRE TV")
    assert [(c[0], c[1], c[2]) for c in calls] == [
        ("unjoin", STR_ZONE, {}),
        ("select_sound_mode", RECEIVER, {"sound_mode": AFD}),
        ("turn_off", RECEIVER, {}),
    ]


async def test_receiver_switched_to_turntable_stays_on(hass: HomeAssistant) -> None:
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, power_off=True, off_mode=AFD)
    await _turn_off_after_music(hass, facade, None, "RETRO HIFI")
    assert [c[0] for c in calls] == ["unjoin"]


async def test_power_off_disabled_only_unjoins(hass: HomeAssistant) -> None:
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE)
    await _turn_off_after_music(hass, facade, None, None)
    assert [c[0] for c in calls] == ["unjoin"]


@pytest.mark.parametrize(("source", "expected"), [(None, ["unjoin", "turn_off"]), ("FIRE TV", ["unjoin"])])
async def test_unknown_join_input_turns_off_only_without_an_input(
    hass: HomeAssistant, source: str | None, expected: list[str]
) -> None:
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, power_off=True)
    hass.states.async_set(STR_ZONE, "idle", {})
    _receiver(hass, source)
    facade._digital_seen_in_sync = True
    await facade.async_power_zone_off()
    assert [c[0] for c in calls] == expected


async def test_receiver_not_in_music_is_left_alone(hass: HomeAssistant) -> None:
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE, power_off=True)
    hass.states.async_set(DECODER, "idle", {"group_members": []})
    hass.states.async_set(STR_ZONE, "idle", {})
    _receiver(hass, None)
    await facade.async_power_zone_off()
    assert [c[0] for c in calls] == ["unjoin"]


@pytest.mark.parametrize("in_music", [False, True])
async def test_receiver_volume_and_mute_only_while_in_music(
    hass: HomeAssistant, in_music: bool
) -> None:
    facade, calls = _facade(hass, ZONE_KIND_DIGITAL, STR_ZONE)
    if in_music:
        facade._session._members = [facade.entity_id]
    await facade.async_set_volume_level(0.4)
    await facade.async_mute_volume(True)
    expected = ["volume_set", "volume_mute"] if in_music else []
    assert [c[0] for c in calls] == expected


async def test_amp_zone_volume_works_when_off(hass: HomeAssistant) -> None:
    hass.states.async_set(AMP_ZONE, "off", {})
    facade, calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE)
    await facade.async_set_volume_level(0.2)
    assert [c[0] for c in calls] == ["volume_set"]


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


async def _member_after(hass: HomeAssistant, monkeypatch, *states: str | None) -> bool:
    """Put a playing amp zone in a group, walk it through states, and say if it stayed."""
    monkeypatch.setattr("custom_components.amp_zone_player.media_player._EXTERNAL_OFF_GRACE_SEC", 0)
    hass.states.async_set(AMP_ZONE, "on", {"source": "WiiM Pro"})
    facade, _calls = _facade(hass, ZONE_KIND_AMP, AMP_ZONE)
    facade.hass = hass
    session = facade._session
    session.register(facade)
    session._members = [facade.entity_id, "media_player.other_facade"]
    session.leader_id = facade.entity_id
    for state in states:
        if state is None:
            hass.states.async_remove(AMP_ZONE)
        else:
            hass.states.async_set(AMP_ZONE, state)
        facade._schedule_amp_external_off()
        if facade._amp_off_task is not None:
            await facade._amp_off_task
    return session.is_member(facade.entity_id)


@pytest.mark.parametrize(
    "states",
    [
        (STATE_UNAVAILABLE,),
        (STATE_UNAVAILABLE, "on"),
        (STATE_UNKNOWN,),
        (None,),
    ],
)
async def test_unavailable_amp_zone_stays_in_its_group(
    hass: HomeAssistant, monkeypatch, states
) -> None:
    assert await _member_after(hass, monkeypatch, *states)


@pytest.mark.parametrize("states", [("off",), (STATE_UNAVAILABLE, "off")])
async def test_amp_zone_really_off_leaves_its_group(
    hass: HomeAssistant, monkeypatch, states
) -> None:
    assert not await _member_after(hass, monkeypatch, *states)
