# Music Assistant Amp Zone Player

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/heatvent/ha-amp-zone-player)](https://github.com/heatvent/ha-amp-zone-player/releases)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg)](https://www.home-assistant.io/)

**GitHub:** [github.com/heatvent/ha-amp-zone-player](https://github.com/heatvent/ha-amp-zone-player)

Use **[Music Assistant](https://www.music-assistant.io/)** with a matrix amp the way Control4 Composer works: play from one room, add other rooms to the session, and control volume per room — without pretending each zone can decode audio.

A streamer (WiiM, etc.) stays the only decoder. Amp zones only turn on/off and change volume on a shared analog feed.

This integration does **not** speak amplifier UDP. It bridges existing Home Assistant entities and is built so Music Assistant can drive them via the **Home Assistant Media Players** provider (HA `join` / `unjoin` grouping). The same entities also work on dashboards and automations.

| Role | What you already have | Used for |
|---|---|---|
| **Zone** | Amp zone `media_player` (e.g. [Control4 Audio](https://github.com/heatvent/ha-c4-audio)) | On / off, volume, mute, optional source |
| **Decoder** | Streamer `media_player` (e.g. WiiM Pro) | Play / pause, queue, artwork, `play_media` |

---

## Composer-style sessions (core idea)

```text
Music Assistant
      │
      ▼
┌──────────────────────────────────┐
│  Session                         │
│  Leader:  Bar Speakers           │  ← play / pause / queue → WiiM
│  Members: Kitchen, Patio, …      │  ← join = zone on; volume per room
└──────────────────────────────────┘
```

| You do this | What happens |
|---|---|
| Play on **Bar Speakers** | Bar becomes **leader**; zone on; stream goes to the WiiM |
| **Group / join** Kitchen + Patio | Those zones turn on and join the session |
| Volume on Kitchen | Kitchen zone volume only |
| Remove / power off Patio | Patio leaves; WiiM keeps playing if others remain |

**Do not** use Music Assistant **SyncGroup** / “Add group player” for these rooms — that is for digitally synced speakers. Use the player **group / members** control (Home Assistant grouping) instead.

---

## How it works

```text
  Music Assistant (HA Media Players provider)
                      │
                      ▼
        ┌─────────────────────────────┐
        │  This integration           │
        │  Leader + joined members    │
        └─────────────┬───────────────┘
               ┌──────┴──────┐
               ▼             ▼
          Amp zones      Decoder (WiiM)
          on / off       play / pause
          volume         next / art
```

One decoder, one queue — many rooms on the same analog stream.

---

## Features

- Built for **Music Assistant** + matrix amp zones (Composer-like add rooms)
- HA `media_player.join` / `unjoin` and `group_members` (GROUPING)
- Shared decoder for playback and metadata
- Optional `select_source` when a zone turns on
- Per-zone volume; last member leaving does not require stopping the decoder early for others
- Any zone entities with power + volume — not Control4-only
- UI config (no YAML)

---

## Requirements

| Need | Example |
|---|---|
| Home Assistant | 2024.12 or newer |
| Music Assistant | With **Home Assistant Media Players** provider (typical use) |
| Decoder | WiiM Pro or any `media_player` that can `play_media` |
| Amp zones | Zone `media_player`s with on/off + volume (e.g. `c4_audio`) |

Amp UDP / chassis control stays in [ha-c4-audio](https://github.com/heatvent/ha-c4-audio) (or similar).

---

## Install (HACS)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Repository: `https://github.com/heatvent/ha-amp-zone-player`
3. Category: **Integration**
4. Download **Music Assistant Amp Zone Player**
5. **Restart** Home Assistant
6. **Settings → Devices & Services → Add Integration → Music Assistant Amp Zone Player**

HACS tracks **GitHub Releases** only (`hide_default_branch`). After a release, use **⋮ → Update information** if the update is slow to appear.

### Manual

Copy `custom_components/amp_zone_player` into `config/custom_components/`, restart, then add the integration.

---

## Setup

1. **Decoder** — WiiM (or other streamer)
2. **Zones** — amp zone `media_player` entities
3. **Amp input / source** — plain-text name from the zone source list (e.g. `WiiM Pro`), or None
4. **Name prefix** — leave blank
5. **Hub name** — optional (blank → `Amp zones`); does not prefix player names

Facade names look like `Bar Speakers`; entity ids like `media_player.bar_speakers` when free.

### Music Assistant

1. Player providers → **Home Assistant Media Players** → enable the facades only  
2. Hide/uncheck the raw WiiM and the raw Control4 zone entities  
3. Select a room → play → use **group / members** to add other facades  
4. Never use **Add group player** / SyncGroup for these

HA join example:

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
| **Play / play_media** | Facade becomes leader; zone on; queue/stream on decoder |
| **Join** | Member zones on; listed in `group_members` |
| **Unjoin / Off / Stop** | That zone off; leaves session |
| **Volume / Mute** | That zone only |
| **Pause / Next / Seek** | Decoder (shared) |

---

## Limits

- **One queue** — all joined rooms share the decoder stream  
- **Not digital sync** — rooms share an analog feed; SyncGroup is the wrong tool  
- **Amp integration required** — this only proxies HA entities  

---

## Support

- Repository: [github.com/heatvent/ha-amp-zone-player](https://github.com/heatvent/ha-amp-zone-player)
- Issues: [github.com/heatvent/ha-amp-zone-player/issues](https://github.com/heatvent/ha-amp-zone-player/issues)
- Amp / switch UDP: [ha-c4-audio](https://github.com/heatvent/ha-c4-audio)

---

## Developers — releasing

HACS uses `manifest.json` `"version"` + a matching GitHub Release tag (`v0.2.1` ↔ `"0.2.1"`).

```powershell
.\tools\release.ps1 0.2.1 -Notes "Short summary for the release"
```
