"""The lead room leaves, TV takes a receiver, and a reload while music plays.

The order of calls is what Music Assistant 2.10 sends; the rig below answers them
the way the amp, the receiver and the decoder do.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.amp_zone_player import media_player as mp
from custom_components.amp_zone_player.const import DOMAIN, ZONE_KIND_AMP, ZONE_KIND_DIGITAL
from custom_components.amp_zone_player.session import AmpSession

DECODER = "media_player.wiim_ma_decoder"
RECEIVER = "media_player.theater_receiver"
KITCHEN, BAR, GARAGE = (f"media_player.{r}_speakers" for r in ("kitchen", "bar", "garage"))
THEATER = "media_player.theater_speakers"
STARTUP = 0.13


def _url(room: str) -> str:
    return f"http://ma.local:8097/flow/abc/{room}/def/item.flac"


class Rig:
    """Rooms with a backend that changes state when it is called."""

    def __init__(self, hass: HomeAssistant, *rooms: str) -> None:
        self.hass = hass
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.offs: list[str] = []
        entry = MockConfigEntry(domain=DOMAIN, data={})
        entry.add_to_hass(hass)
        self.session = AmpSession(hass, entry.entry_id)
        self.rooms: dict[str, mp.AmpZoneFacade] = {}
        self.decoder("idle", None, [DECODER])
        for room in rooms:
            digital = room == THEATER
            facade = mp.AmpZoneFacade(
                hass=hass,
                entry=entry,
                session=self.session,
                zone_entity_id=self.zone(room),
                decoder_entity_id=DECODER,
                playback_entity_id=None,
                source_name=None if digital else "WiiM Pro",
                name_prefix="",
                zone_kind=ZONE_KIND_DIGITAL if digital else ZONE_KIND_AMP,
                startup_volume=STARTUP,
                power_off=digital,
            )
            facade.entity_id = room
            async_track_state_change_event(hass, [DECODER], facade._note_feed_change)
            facade._async_call = self._call  # type: ignore[method-assign]
            self.rooms[room] = self.session._facades[room] = facade
            state = "idle" if digital else "off"
            hass.states.async_set(self.zone(room), state, {"volume_level": 0.1})
            if digital:
                hass.states.async_set(RECEIVER, "on", {"source": "FIRE TV"})

    @staticmethod
    def zone(room: str) -> str:
        if room == THEATER:
            return "media_player.theater_str"
        return room.replace("_speakers", "").replace("media_player.", "media_player.amp_")

    def decoder(self, state: str, url: str | None, group: list[str] | None = None) -> None:
        if group is None:
            group = self.hass.states.get(DECODER).attributes["group_members"]
        self.hass.states.async_set(
            DECODER, state, {"media_content_id": url, "group_members": list(group)}
        )

    async def _call(self, service, entity_id, data=None, *, critical=True) -> bool:
        data = data or {}
        self.calls.append((service, entity_id, data))
        state = self.hass.states.get(entity_id)
        attrs = dict(state.attributes)
        feed = self.hass.states.get(DECODER)
        url, group = feed.attributes["media_content_id"], feed.attributes["group_members"]
        if service == "play_media":
            self.decoder("playing", data["media_content_id"])
        elif service == "media_stop":
            self.decoder("idle", None)
        elif service == "join":
            self.decoder(feed.state, url, [DECODER, *data["group_members"]])
        elif service == "unjoin":
            self.decoder(feed.state, url, [m for m in group if m != entity_id])
        elif service == "turn_on" and state.state == "off":
            attrs |= {"source": "WiiM Pro", "is_volume_muted": False}
            self.hass.states.async_set(entity_id, "on", attrs)
        elif service == "turn_off":
            self.offs.append(entity_id)
            self.hass.states.async_set(entity_id, "off", attrs)
        elif service in ("volume_set", "volume_mute"):
            self.hass.states.async_set(entity_id, state.state, attrs | data)
        return True

    async def play(self, lead: str, *others: str) -> None:
        """Music plays with these rooms, set to 10%, and everything has settled."""
        await self.rooms[lead].async_play_media("music", _url(lead))
        await self.session.async_join(lead, list(others))
        for room in (lead, *others):
            self.set(room, volume_level=0.1)
            self.rooms[room]._turned_on_at = None
        self.calls.clear()

    def set(self, room: str, **attrs: Any) -> None:
        state = self.hass.states.get(self.zone(room))
        self.hass.states.async_set(self.zone(room), state.state, {**state.attributes, **attrs})

    def attr(self, room: str, name: str) -> Any:
        return self.hass.states.get(self.zone(room)).attributes.get(name)

    def outside_off(self, room: str) -> None:
        zone = self.zone(room)
        self.hass.states.async_set(zone, "off", self.hass.states.get(zone).attributes)

    def on(self, room: str) -> bool:
        return self.hass.states.get(self.zone(room)).state != "off"

    def volume(self, room: str) -> float:
        return self.attr(room, "volume_level")

    def playing(self) -> str | None:
        state = self.hass.states.get(DECODER)
        return state.attributes["media_content_id"] if state.state == "playing" else None

    def forget(self) -> None:
        """What a reload leaves behind: nothing."""
        self.session._members, self.session.leader_id = [], None

    # What Music Assistant does.

    async def ma_transfer(self, old: str, new: str, *others: str) -> None:
        await self.rooms[new].async_unjoin_player()
        if self.on(old):
            await self.rooms[old].async_media_stop()
        for room in others:
            await self.rooms[room].async_unjoin_player()
            await self.rooms[room].async_turn_on()
            await self.rooms[new].async_join_players([room])
        await self.rooms[new].async_turn_on()
        await self.rooms[new].async_play_media("music", _url(new))

    async def ma_off(self, old: str, new: str, *others: str) -> None:
        await self.ma_transfer(old, new, *others)
        await self.rooms[old].async_media_stop()  # the late one
        await self.rooms[old].async_turn_off()


@pytest.fixture
def rig(hass: HomeAssistant, monkeypatch):
    monkeypatch.setattr(mp, "_RECEIVER_OFF_DELAY_SEC", 0.05)
    rigs: list[Rig] = []

    def make(*rooms: str) -> Rig:
        rigs.append(Rig(hass, *rooms))
        return rigs[-1]

    yield make
    for made in rigs:
        for facade in made.rooms.values():
            facade._cancel_background_tasks()


# Lead room turned off outside (Control4).


async def test_lead_turned_off_outside_stays_off(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    r.outside_off(KITCHEN)
    await r.ma_transfer(KITCHEN, BAR)
    assert not r.on(KITCHEN)
    assert (r.on(BAR), r.volume(BAR)) == (True, 0.1)
    assert r.session.members == [BAR]
    assert r.session.leader_id == BAR
    assert r.playing() == _url(BAR)


async def test_lead_turned_off_outside_with_three_rooms(rig) -> None:
    r = rig(KITCHEN, BAR, GARAGE)
    await r.play(KITCHEN, BAR, GARAGE)
    r.outside_off(KITCHEN)
    await r.ma_transfer(KITCHEN, BAR, GARAGE)
    assert not r.on(KITCHEN)
    assert r.session.members == [BAR, GARAGE]
    assert r.session.leader_id == BAR
    assert (r.volume(BAR), r.volume(GARAGE)) == (0.1, 0.1)


async def test_turning_a_room_on_never_powers_the_leader(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN)
    # Off a moment after a turn on: not certain yet, so it stays a member.
    r.outside_off(KITCHEN)
    r.rooms[KITCHEN]._turned_on_at = mp.time.monotonic()
    await r.rooms[BAR].async_turn_on()
    assert r.session.members == [KITCHEN, BAR]
    assert not r.on(KITCHEN)
    assert r.on(BAR)


async def test_room_turned_on_does_not_join_a_lead_that_is_off(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN)
    r.outside_off(KITCHEN)
    await r.rooms[BAR].async_turn_on()
    assert r.session.members == [BAR]
    assert r.session.leader_id == BAR


async def test_joining_rooms_does_not_bring_back_a_room_that_is_off(rig) -> None:
    r = rig(KITCHEN, BAR, GARAGE)
    await r.play(KITCHEN, BAR)
    r.outside_off(BAR)
    await r.rooms[KITCHEN].async_join_players([GARAGE])
    assert r.session.members == [KITCHEN, GARAGE]
    assert not r.on(BAR)


async def test_playing_in_another_room_forgets_a_lead_that_is_off(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN)
    r.outside_off(KITCHEN)
    await r.rooms[BAR].async_play_media("music", _url(BAR))
    assert r.session.members == [BAR]


async def test_turning_on_the_lead_itself_still_works(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    r.outside_off(KITCHEN)
    await r.rooms[KITCHEN].async_turn_on()
    assert r.on(KITCHEN)
    assert r.session.members == [KITCHEN, BAR]


async def test_turning_on_a_member_that_plays_sends_nothing(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    r.set(BAR, is_volume_muted=True)
    await r.rooms[BAR].async_turn_on()
    assert r.calls == []


async def test_member_turned_off_outside_can_be_turned_on_again(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    r.outside_off(BAR)
    await r.rooms[BAR].async_turn_on()
    assert (r.on(BAR), r.volume(BAR)) == (True, STARTUP)
    assert r.session.members == [KITCHEN, BAR]


async def test_unavailable_lead_keeps_its_group(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN)
    r.hass.states.async_set(r.zone(KITCHEN), "unavailable")
    await r.rooms[BAR].async_turn_on()
    assert r.session.members == [KITCHEN, BAR]
    assert r.zone(KITCHEN) not in [c[1] for c in r.calls]


# Lead room turned off in Music Assistant.


async def test_late_stop_of_the_old_lead_keeps_the_music(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    await r.ma_off(KITCHEN, BAR)
    assert r.playing() == _url(BAR)
    assert (r.on(KITCHEN), r.on(BAR), r.volume(BAR)) == (False, True, 0.1)
    assert r.session.members == [BAR]


async def test_late_stop_with_three_rooms(rig) -> None:
    r = rig(KITCHEN, BAR, GARAGE)
    await r.play(KITCHEN, BAR, GARAGE)
    await r.ma_off(KITCHEN, BAR, GARAGE)
    assert r.playing() == _url(BAR)
    assert not r.on(KITCHEN)
    assert (r.volume(BAR), r.volume(GARAGE)) == (0.1, 0.1)
    assert r.session.members == [BAR, GARAGE]


async def test_late_stop_right_after_a_reload(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    r.forget()
    await r.session.async_restore_from_zones()
    await r.ma_off(KITCHEN, BAR)
    assert r.playing() == _url(BAR)


async def test_back_and_forth(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    await r.ma_off(KITCHEN, BAR)
    await r.rooms[KITCHEN].async_turn_on()
    await r.ma_off(BAR, KITCHEN)
    assert r.playing() == _url(KITCHEN)
    assert r.session.members == [KITCHEN]


@pytest.mark.parametrize("room", [KITCHEN, BAR])
async def test_stop_works_in_a_settled_group(rig, room) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    await r.rooms[room].async_media_stop()
    assert r.playing() is None


async def test_stop_of_the_new_lead_works_at_once(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    await r.ma_off(KITCHEN, BAR)
    await r.rooms[BAR].async_media_stop()
    assert r.playing() is None


async def test_stop_of_the_old_lead_works_again_later(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    await r.ma_transfer(KITCHEN, BAR)
    room, at = r.session._late_stop
    r.session._late_stop = (room, at - 6)
    await r.rooms[KITCHEN].async_media_stop()
    assert r.playing() is None


async def test_a_lead_that_moved_long_ago_can_stop(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    await r.ma_transfer(KITCHEN, BAR)
    room, at = r.session._former_leader
    r.session._former_leader = (room, at - 20)
    await r.rooms[BAR].async_play_media("music", _url(BAR) + "2")
    await r.rooms[KITCHEN].async_media_stop()
    assert r.playing() is None


# Volume and mute of a room that comes right back.


async def test_room_that_comes_right_back_keeps_its_mute(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    r.set(BAR, is_volume_muted=True)
    await r.ma_off(KITCHEN, BAR)
    assert r.attr(BAR, "is_volume_muted") is True
    assert r.volume(BAR) == 0.1


async def test_room_turned_on_later_starts_at_its_volume(rig) -> None:
    r = rig(KITCHEN, BAR)
    await r.play(KITCHEN, BAR)
    r.set(BAR, is_volume_muted=True)
    await r.rooms[BAR].async_turn_off()
    left = r.rooms[BAR]._left
    r.rooms[BAR]._left = (left[0] - 6, *left[1:])
    await r.rooms[BAR].async_turn_on()
    assert r.volume(BAR) == STARTUP
    assert r.attr(BAR, "is_volume_muted") is False


# Receivers.


async def _receiver_joins(r: Rig, monkeypatch) -> mp.AmpZoneFacade:
    """Music plays in the Kitchen; the Theater receiver joins with its last volume."""
    monkeypatch.setattr(mp, "_STARTUP_VOLUME_SETTLE_SEC", 0)
    await r.play(KITCHEN)
    r.set(THEATER, volume_level=0.33)
    await r.session.async_join(KITCHEN, [THEATER])
    assert r.volume(THEATER) == STARTUP
    # The receiver takes the AirPlay stream and reports its own last volume.
    r.hass.states.async_set(r.zone(THEATER), "playing", {
        **r.hass.states.get(r.zone(THEATER)).attributes, "volume_level": 0.33})
    return r.rooms[THEATER]


async def test_receiver_gets_its_startup_volume_once_it_plays(rig, monkeypatch) -> None:
    r = rig(KITCHEN, THEATER)
    facade = await _receiver_joins(r, monkeypatch)
    facade._schedule_startup_volume_on_play()
    await r.hass.async_block_till_done()
    assert r.volume(THEATER) == STARTUP
    # Only once: a later change by the listener stays.
    r.set(THEATER, volume_level=0.25)
    facade._schedule_startup_volume_on_play()
    await r.hass.async_block_till_done()
    assert r.volume(THEATER) == 0.25


async def test_receiver_that_plays_long_after_joining_keeps_its_volume(rig, monkeypatch) -> None:
    r = rig(KITCHEN, THEATER)
    facade = await _receiver_joins(r, monkeypatch)
    facade._startup_volume_due -= mp._STARTUP_VOLUME_WINDOW_SEC + 1
    facade._schedule_startup_volume_on_play()
    await r.hass.async_block_till_done()
    assert r.volume(THEATER) == 0.33


async def test_receiver_that_left_before_playing_keeps_its_volume(rig, monkeypatch) -> None:
    r = rig(KITCHEN, THEATER)
    facade = await _receiver_joins(r, monkeypatch)
    await facade.async_turn_off()
    r.hass.states.async_set(r.zone(THEATER), "playing", {"volume_level": 0.33})
    facade._schedule_startup_volume_on_play()
    await r.hass.async_block_till_done()
    assert r.volume(THEATER) == 0.33


async def _receiver_plays(r: Rig) -> None:
    await r.play(KITCHEN, BAR, THEATER)
    facade = r.rooms[THEATER]
    assert facade._digital_in_sync_group()
    facade._digital_seen_in_sync = True
    facade._remember_receiver_source()


def _tv_takes_theater(r: Rig) -> None:
    feed = r.hass.states.get(DECODER)
    group = [m for m in feed.attributes["group_members"] if m != r.zone(THEATER)]
    r.decoder(feed.state, feed.attributes["media_content_id"], group)


@pytest.mark.parametrize("state", ["playing", "paused"])
async def test_tv_takeover_leaves_the_receiver_on(rig, state) -> None:
    r = rig(KITCHEN, BAR, THEATER)
    await _receiver_plays(r)
    r.decoder(state, _url(KITCHEN))
    _tv_takes_theater(r)  # Sony still says FIRE TV, the input it joined on.
    await r.rooms[THEATER].async_unjoin_player()
    await asyncio.sleep(0.1)
    assert r.offs == []
    assert r.session.members == [KITCHEN, BAR]


async def test_room_off_turns_the_receiver_off(rig) -> None:
    r = rig(KITCHEN, BAR, THEATER)
    await _receiver_plays(r)
    await r.rooms[THEATER].async_turn_off()
    await asyncio.sleep(0.1)
    assert r.offs == [RECEIVER]


async def test_last_room_off_turns_the_receiver_off_at_once(rig) -> None:
    r = rig(KITCHEN, BAR, THEATER)
    await _receiver_plays(r)
    for room in (KITCHEN, BAR, THEATER):
        await r.rooms[room].async_turn_off()
    assert RECEIVER in r.offs


async def test_receiver_off_after_the_music_stopped_first(rig) -> None:
    r = rig(KITCHEN, BAR, THEATER)
    await _receiver_plays(r)
    r.decoder("idle", None, [DECODER])
    await r.rooms[THEATER].async_turn_off()
    await asyncio.sleep(0.1)
    assert r.offs == [RECEIVER]


@pytest.mark.parametrize("new", [BAR, THEATER])
async def test_receiver_stays_on_when_the_lead_room_leaves(rig, new) -> None:
    r = rig(KITCHEN, BAR, THEATER)
    await _receiver_plays(r)
    await r.ma_off(KITCHEN, new, BAR if new == THEATER else THEATER)
    await asyncio.sleep(0.1)
    assert RECEIVER not in r.offs
    assert r.volume(THEATER) == 0.1
    assert r.rooms[THEATER]._digital_in_sync_group()
    assert r.playing() == _url(new)


async def test_receiver_switched_during_the_wait_stays_on(rig) -> None:
    r = rig(KITCHEN, BAR, THEATER)
    await _receiver_plays(r)
    await r.rooms[THEATER].async_turn_off()
    r.hass.states.async_set(RECEIVER, "on", {"source": "GAME"})
    await asyncio.sleep(0.1)
    assert r.offs == []


# Reload and restart while music plays.


async def test_reload_restores_the_lead_from_the_stream(rig) -> None:
    r = rig(BAR, GARAGE, KITCHEN)
    await r.play(KITCHEN, BAR)
    r.forget()
    await r.session.async_restore_from_zones()
    assert r.session.leader_id == KITCHEN
    assert r.session.members == [KITCHEN, BAR]


@pytest.mark.parametrize("url", [None, "http://x/other.mp3", _url(GARAGE)])
async def test_lead_is_corrected_when_the_stream_shows_up_later(rig, url) -> None:
    r = rig(BAR, GARAGE, KITCHEN)
    await r.play(KITCHEN, BAR)
    r.decoder("playing", url)
    r.forget()
    await r.session.async_restore_from_zones()
    assert r.session.members == [BAR, KITCHEN]
    r.decoder("playing", _url(KITCHEN))
    r.session.async_feed_changed()
    assert r.session.leader_id == KITCHEN
    assert r.session.members == [KITCHEN, BAR]


async def test_known_lead_is_never_changed_by_the_stream(rig) -> None:
    r = rig(BAR, KITCHEN)
    await r.play(KITCHEN, BAR)
    r.decoder("playing", _url(BAR))
    r.session.async_feed_changed()
    assert r.session.leader_id == KITCHEN


async def test_restore_waits_for_home_assistant_to_start(rig, hass: HomeAssistant) -> None:
    r = rig(BAR, KITCHEN)
    await r.play(KITCHEN, BAR)
    r.forget()
    r.session._facades = {}
    hass.set_state(CoreState.starting)
    r.session.expect(2)
    for facade in r.rooms.values():
        r.session.register(facade)
    await hass.async_block_till_done()
    assert r.session.members == []
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert r.session.members == [KITCHEN, BAR]
