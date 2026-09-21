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
| **Decoder** | Streamer `media_player` (e.g. WiiM Pro) | Play / pause, stop, artwork, `play_media` |

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
          on / off       play_media / pause
          volume         stop / next / art
```

One decoder, one queue — many rooms on the same analog stream.

---

## Features

- Built for **Music Assistant** + matrix amp zones (Composer-like add rooms)
- HA `media_player.join` / `unjoin` and `group_members` (GROUPING)
- Shared decoder for playback and metadata
- Optional `select_source` when a zone turns on
- Per-zone volume; leaving a room does not stop the decoder for others
- Zone picker lists **Control4 Audio** speaker zones only (e.g. Bar Speakers)
- UI config (no YAML)

---

## Requirements

| Need | Example |
|---|---|
| Home Assistant | 2024.12 or newer |
| Music Assistant | With **Home Assistant Media Players** provider (typical use) |
| Decoder | WiiM Pro or any `media_player` that can `play_media` with a URL |
| Amp zones | [Control4 Audio](https://github.com/heatvent/ha-c4-audio) speaker-zone `media_player`s |

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

1. **Decoder** — WiiM (analog out → amp input 1)
2. **Zones** — Control4 Audio **speaker** zones only (Bar Speakers, Kitchen Speakers, …). The bare Control4 Amp / Switch player is hidden.
3. **Queue / SyncGroup player (optional)** — your Music Assistant **House** group (see below). Play/pause goes there so Sonys stay in sync; zones only open the WiiM analog feed.
4. **Amp input / source** — plain-text name from the zone source list (e.g. `WiiM Pro`), or None
5. **Name prefix** — leave blank
6. **Hub name** — optional (blank → `Amp zones`); does not prefix player names

Facade names look like `Bar Speakers`; entity ids like `media_player.bar_speakers` when free.

### Music Assistant — amp rooms only

1. Player providers → **Home Assistant Media Players** → enable the facades only  
2. Hide/uncheck the raw WiiM and the raw Control4 zone entities  
3. Select a room → play → use **group / members** to add other facades  
4. Do **not** put amp facades in a SyncGroup with each other (analog feed, not digital sync)  
5. If audio cuts out mid-stream, try changing the facade’s **HTTP Profile** in MA player settings

### Music Assistant — House (WiiM + Sony receivers)

Use this when theater/basement Sonys should play with the WiiM (and amp ceilings via analog).

1. In MA: **Settings → Players → Add group player**  
2. Choose a **native Sync Group** (perfect sync), not Universal Group  
3. Name it **House**  
4. Members: **WiiM** + both **STR-AZ1000ES** players (Cast / AirPlay / Sendspin — whichever groups cleanly)  
5. Save. Optionally enable **dynamic members** if you sometimes drop a Sony  
6. On each Sony player: **Stereo / Direct** (or Pure Direct) for music; tune **Static playback delay** if a room echoes  
7. Expose **House** to Home Assistant (Music Assistant integration → that player enabled)  
8. Amp Zone Player → **Configure** → set **Queue / SyncGroup player** to `media_player.house` (or whatever entity id House got)  
9. In MA player list: use **House** and/or the **facades**; hide raw WiiM if you like  

**Day-to-day**

| Goal | Do this |
|---|---|
| Amp rooms only | Play to a facade; join other facades. Leave House/Sonys off. |
| Sonys + optional amp | Play to **House**. Turn on / join the facades you want (source = WiiM). |
| New track from a facade with House configured | Play on the facade — queue goes to **House** (Sonys stay in the group). |

HA join example (amp zones only):

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
| **Play / play_media** | Facade becomes leader; zone on; queue on **playback** target (House SyncGroup if set, else WiiM) |
| **Join** | Member zones on; listed in `group_members` (adds merge — does not replace) |
| **Unjoin / Off** | That zone off; leaves session; queue keeps playing if others remain |
| **Stop** | Stops (or pauses) the **playback** target — silence for that queue (and Sonys if House) |
| **Volume / Mute** | That zone only |
| **Pause / Next / Seek** | Playback target (shared) |

---

## Limits

- **One queue** — all joined amp rooms share the WiiM analog feed  
- **Amp facades are not digital sync members** — put **WiiM + Sonys** in a SyncGroup; facades only open amp zones  
- **Amp integration required** — this only proxies HA entities  
- **Amp source name must match** — if set, it must match the zone `source_list` exactly or you get silence while the WiiM plays  

---

## Troubleshooting

| Symptom | Check |
|---|---|
| No music | Decoder / House can play a URL in HA; facade logs `play_media → …`; amp source spelling |
| Third room replaces second | Update to **0.2.2+** (join merges members) |
| Group works, still silence | WiiM playing in HA? Amp input selected? Zone volume > 0? |
| Mid-stream dropouts | MA player setting **HTTP Profile** (try each option) |
| Echo vs Sonys | SyncGroup members only; Stereo/Direct on AVR; Static playback delay on the late room |

---

## Support

- Repository: [github.com/heatvent/ha-amp-zone-player](https://github.com/heatvent/ha-amp-zone-player)
- Issues: [github.com/heatvent/ha-amp-zone-player/issues](https://github.com/heatvent/ha-amp-zone-player/issues)
- Amp / switch UDP: [ha-c4-audio](https://github.com/heatvent/ha-c4-audio)

---

## Developers — releasing

HACS uses `manifest.json` `"version"` + a matching GitHub Release tag (`v0.2.4` ↔ `"0.2.4"`).

```powershell
.\tools\release.ps1 0.2.4 -Notes "Short summary for the release"
```
