# Matrix Amplifier Zone Player

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/heatvent/ha-amp-zone-player)](https://github.com/heatvent/ha-amp-zone-player/releases)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg)](https://www.home-assistant.io/)

**GitHub:** [github.com/heatvent/ha-amp-zone-player](https://github.com/heatvent/ha-amp-zone-player)

Turn **matrix amplifier zones** into normal Home Assistant `media_player` entities by bridging each zone to a shared decoder (streamer).

This integration does **not** talk to the amplifier over UDP or any amp protocol. It controls existing Home Assistant entities:

| Role | What you already have | What this integration uses it for |
|---|---|---|
| **Zone** | Amp zone `media_player` (e.g. [Control4 Audio](https://github.com/heatvent/ha-c4-audio)) | On / off, volume, mute, optional source select |
| **Decoder** | Real streamer `media_player` (e.g. WiiM Pro) | Play / pause, next, seek, queue, artwork, `play_media` |

Each configured zone becomes one facade player (e.g. `Bar Speakers`). Facades support **Home Assistant player grouping** (join / unjoin) so you can use them like Control4 Composer: play from one room, add other rooms to the session, and set volume per room. That works in HA and in **[Music Assistant](https://www.music-assistant.io/)** via the Home Assistant Media Players provider.

---

## How it works

```text
  Music Assistant · dashboards · automations · voice
                      │
                      ▼
        ┌─────────────────────────────┐
        │  Session (this integration) │
        │  Leader: Bar Speakers       │  ← queue / play / pause
        │  Members: Kitchen, Patio …  │  ← on/off + volume only
        └─────────────┬───────────────┘
               ┌──────┴──────┐
               ▼             ▼
          Amp zones      Decoder (WiiM)
          on / off       play / pause
          volume         next / art
          mute           play_media
```

One decoder, one queue — many rooms on the same analog stream. Join turns a zone on into the session; unjoin turns it off. The decoder keeps playing until the last member leaves.

**Music Assistant:** enable the facade players under Home Assistant Media Players (hide the raw WiiM). Select a room and play, then use MA’s **group / member** controls (HA grouping) to add other amp facades — not SyncGroup / “Add group player” (those are for digitally synced speakers).

---

## Features

- One HA `media_player` per amp zone
- **Composer-style session:** `media_player.join` / `unjoin` + `group_members` (HA GROUPING)
- Shared decoder for playback, metadata, and `play_media`
- Optional `select_source` when a zone turns on
- Per-zone volume; turning a room off does not stop the decoder if other members remain
- Works with any zone entities that support power + volume — not Control4-specific
- Configure from the UI (no YAML)

---

## Requirements

| Need | Example |
|---|---|
| Home Assistant | 2024.12 or newer |
| Decoder | WiiM Pro, or any `media_player` that can play media |
| Amp zones | Zone `media_player`s with on/off + volume (e.g. `c4_audio` zones) |

Amp chassis control (UDP, routing, EQ, etc.) stays in a separate integration such as [ha-c4-audio](https://github.com/heatvent/ha-c4-audio).

---

## Install

### HACS (recommended)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Repository: `https://github.com/heatvent/ha-amp-zone-player`
3. Category: **Integration**
4. Download **Matrix Amplifier Zone Player** (choose a release version)
5. **Restart** Home Assistant
6. **Settings → Devices & Services → Add Integration → Matrix Amplifier Zone Player**

> HACS follows **GitHub Releases** only (not `main`). New versions show up after a tagged release.

### Manual

Copy `custom_components/amp_zone_player` into your Home Assistant `config/custom_components/` folder, restart, then add the integration.

---

## Setup

1. **Decoder** — the real streamer that plays content
2. **Zones** — one or more amp zone `media_player` entities
3. **Amp input / source** — pick from the dropdown built from each zone’s **source list** (same plain-text labels as the zone Source control, e.g. `WiiM Pro`). This is **not** an entity. Choose **None** to skip auto-routing, or type the exact label if it is missing from the list.
4. **Name prefix** *(optional)* — leave blank unless you want a prefix on facade names
5. **Hub name** *(optional)* — blank becomes `Amp zones`; labels the integration entry only and does **not** prefix player names

Facade names are short room labels (e.g. `Bar Speakers`), derived from the zone — not the hub title. Entity ids use that label (`media_player.bar_speakers`) when free.

### Using with Music Assistant

1. Settings → Player providers → **Home Assistant Media Players**
2. Select the facade players (e.g. `Bar Speakers`) — not the raw Control4 zone entities and not the raw WiiM
3. Hide or disable the decoder in MA if it duplicates the facades

**Play like Composer**

1. Select a room (e.g. **Bar Speakers**) and play — that room is the session **leader**; audio goes to the WiiM
2. Use the player **group / members** control to add Kitchen, Patio, etc. (HA join) — those zones turn on
3. Adjust **per-room volume** on each member; remove a room (unjoin / power off) to leave the session
4. Do **not** use Settings → Add group player / SyncGroup for these facades

You can also join from HA:

```yaml
action: media_player.join
target:
  entity_id: media_player.bar_speakers
data:
  group_members:
    - media_player.kitchen_speakers
    - media_player.patio_speakers
```

---

## Behavior

| Action | Result |
|---|---|
| **Play / play_media** on a facade | That facade becomes leader; zone on; stream/queue on decoder |
| **Join** other facades | Those zones on; added to `group_members` |
| **Unjoin / Turn off / Stop** | That zone off; leaves session; decoder keeps going if others remain |
| **Volume / Mute** | That zone only |
| **Pause / Next / Previous / Seek** | Decoder (shared) |

---

## Limits

- **One queue.** Kitchen and Patio cannot play different tracks through this bridge — they share the decoder.
- **Not multi-room sync hardware.** Groups mean “several rooms hearing the same analog feed,” not Sonos-style independent players.
- **Amp still needs its own integration.** This package only proxies existing HA entities; pair it with something like [ha-c4-audio](https://github.com/heatvent/ha-c4-audio) for the chassis.

---

## Support

- Repository: [github.com/heatvent/ha-amp-zone-player](https://github.com/heatvent/ha-amp-zone-player)
- Issues: [github.com/heatvent/ha-amp-zone-player/issues](https://github.com/heatvent/ha-amp-zone-player/issues)
- Amp / switch UDP control: [ha-c4-audio](https://github.com/heatvent/ha-c4-audio)

---

## Developers — releasing

HACS updates from **GitHub Releases** and the `"version"` field in `custom_components/amp_zone_player/manifest.json` — not from the README badge. Tag and manifest version must match (`v0.1.9` ↔ `"0.1.9"`).

From a clean `main`:

```powershell
.\tools\release.ps1 0.1.9 -Notes "Short summary for the release"
```

Bumps `manifest.json`, updates the changelog, tags `vX.Y.Z`, and publishes the GitHub Release HACS reads. After a release, in HACS use **⋮ → Update information** (or reload HACS) if the update does not appear right away.
