"""Shared listening session — Composer-style leader + joinable zones."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from .media_player import AmpZoneFacade

_LOGGER = logging.getLogger(__name__)


class AmpSession:
    """
    One shared music session per config entry.

    Leader receives play/queue (forwards to the decoder). Other members are
    zones that hear the same stream — join turns them on, unjoin turns them off.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.leader_id: str | None = None
        self._members: list[str] = []  # facade entity_ids, leader first
        self._facades: dict[str, AmpZoneFacade] = {}  # facade entity_id -> entity
        self._zone_to_facade: dict[str, str] = {}  # zone media_player -> facade
        self._listeners: list[Callable[[], None]] = []

    def register(self, facade: AmpZoneFacade) -> None:
        """Register a facade once its entity_id is known."""
        assert facade.entity_id
        self._facades[facade.entity_id] = facade
        self._zone_to_facade[facade.zone_entity_id] = facade.entity_id

    def unregister(self, facade: AmpZoneFacade) -> None:
        self._facades.pop(facade.entity_id, None)
        self._zone_to_facade.pop(facade.zone_entity_id, None)
        if facade.entity_id in self._members:
            self._members = [m for m in self._members if m != facade.entity_id]
            if self.leader_id == facade.entity_id:
                self.leader_id = self._members[0] if self._members else None

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def async_notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @property
    def members(self) -> list[str]:
        return list(self._members)

    def group_members_for(self, facade_entity_id: str) -> list[str]:
        """HA group_members: leader first. Solo player lists only itself."""
        if facade_entity_id not in self._members:
            return [facade_entity_id]
        if self.leader_id and self.leader_id in self._members:
            rest = [m for m in self._members if m != self.leader_id]
            return [self.leader_id, *rest]
        return list(self._members)

    def is_leader(self, facade_entity_id: str) -> bool:
        return self.leader_id == facade_entity_id

    def is_member(self, facade_entity_id: str) -> bool:
        return facade_entity_id in self._members

    def facade_for_entity(self, entity_id: str) -> AmpZoneFacade | None:
        return self._facades.get(entity_id)

    def known_facade_ids(self) -> set[str]:
        return set(self._facades)

    async def async_ensure_leader(self, facade_entity_id: str) -> None:
        """Make this facade the session leader and a member (zone on)."""
        facade = self._facades.get(facade_entity_id)
        if facade is None:
            return
        await facade.async_power_zone_on()
        if facade_entity_id not in self._members:
            if self.leader_id and self.leader_id in self._members:
                # Insert as new leader, keep existing members.
                self._members = [
                    facade_entity_id,
                    *[m for m in self._members if m != facade_entity_id],
                ]
            else:
                self._members = [facade_entity_id]
        else:
            # Move to front as leader.
            self._members = [
                facade_entity_id,
                *[m for m in self._members if m != facade_entity_id],
            ]
        self.leader_id = facade_entity_id
        self.async_notify()

    async def async_join(
        self, leader_entity_id: str, group_members: list[str]
    ) -> None:
        """
        Add group_members to the session with leader as coordinator.

        Music Assistant often calls join once per newly checked player (only
        that entity in group_members). Merge into the existing session instead
        of replacing it, or a third room would knock out the second.
        """
        leader = self._facades.get(leader_entity_id)
        if leader is None:
            _LOGGER.warning("Join ignored — unknown leader %s", leader_entity_id)
            return

        await leader.async_power_zone_on()

        # Start from current session (leader first), then add newcomers.
        members: list[str] = []
        if self.leader_id == leader_entity_id and self._members:
            members = [
                leader_entity_id,
                *[m for m in self._members if m != leader_entity_id],
            ]
        elif leader_entity_id in self._members:
            # Another facade was leader; this one takes over, keep others.
            members = [
                leader_entity_id,
                *[m for m in self._members if m != leader_entity_id],
            ]
        else:
            members = [leader_entity_id]
            for existing in self._members:
                if existing != leader_entity_id and existing in self._facades:
                    members.append(existing)

        for entity_id in group_members:
            if entity_id == leader_entity_id:
                continue
            if entity_id not in self._facades:
                _LOGGER.warning(
                    "Join skipped %s — not a Music Assistant Amp Zone Player facade",
                    entity_id,
                )
                continue
            if entity_id in members:
                continue
            member = self._facades[entity_id]
            await member.async_power_zone_on()
            members.append(entity_id)

        self.leader_id = leader_entity_id
        self._members = members
        _LOGGER.info(
            "Session group: leader=%s members=%s", self.leader_id, self._members
        )
        self.async_notify()

    async def async_unjoin(self, facade_entity_id: str) -> None:
        """Remove a facade from the session and power its zone off."""
        facade = self._facades.get(facade_entity_id)
        if facade is not None:
            await facade.async_power_zone_off()

        if facade_entity_id not in self._members:
            self.async_notify()
            return

        self._members = [m for m in self._members if m != facade_entity_id]
        if self.leader_id == facade_entity_id:
            self.leader_id = self._members[0] if self._members else None
            _LOGGER.info("Session leader moved to %s", self.leader_id)

        self.async_notify()

    def any_other_member_on(self, facade_entity_id: str) -> bool:
        return any(m != facade_entity_id for m in self._members)
