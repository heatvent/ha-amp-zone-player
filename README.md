# Music Assistant Amp Zone Player

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/heatvent/ha-amp-zone-player)](https://github.com/heatvent/ha-amp-zone-player/releases)
[![HA](https://img.shields.io/badge/Home%20Assistant-2025.12%2B-blue.svg)](https://www.home-assistant.io/)

**GitHub:** [github.com/heatvent/ha-amp-zone-player](https://github.com/heatvent/ha-amp-zone-player)

Use **[Music Assistant](https://www.music-assistant.io/)** with a matrix amp the way Control4 Composer works: play from one room, add other rooms to the session, and control volume per room — without pretending each zone can decode audio.

A streamer (WiiM, etc.) stays the only device that feeds the amp. Amp zones only turn on/off, select an input, and change volume on that shared analog feed.

This integration does **not** speak amplifier UDP. It bridges existing Home Assistant `media_player` entities so Music Assistant (and dashboards / automations) can drive them through the **Home Assistant Media Players** provider.

| Role | What you configure | Used for |
|---|---|---|
| **Zone** | Amp/matrix zone `media_player` (e.g. [Control4 Audio](https://github.com/heatvent/ha-c4-audio) speaker zones) | On / off, volume, mute, optional source |
| **Decoder** | Streamer `media_player` (e.g. WiiM Pro) wired to the amp | Analog feed + fallback queue target |
| **Playback (optional)** | MA SyncGroup / other queue player (e.g. `House`) | Play / pause / stop / next when Sonys should sync with the WiiM |

---

## How it works

```text
  Music Assistant · dashboards · automations · voice
                      │
                      ▼
        ┌─────────────────────────────────────┐
        │  Facade players (this integration)  │
        │  Leader + joined amp rooms          │
        │  Volume / join / unjoin per room    │
        └───────────────┬─────────────────────┘
                 ┌──────┴───────┐
                 ▼              ▼
            Amp zones      Playback target
            on / off       (SyncGroup if set,
            volume          else decoder/WiiM)
            select_source      │
                               ▼
                         Decoder (WiiM)
                         analog → amp input
```

**Two layers (do not mix them up):**

1. **Amp session (this integration)** — HA `join` / `unjoin` among facade players. Turns zones on/off on one analog feed. Not digital sync.
2. **Digital SyncGroup (Music Assistant)** — WiiM + Cast/AirPlay/Sendspin players (e.g. Sony AVRs). Optional; set as **Queue / SyncGroup player** so facade Play drives that group while amp rooms still open the WiiM feed.

```text
You play on Bar Speakers (facade)
        │
        ├─► Amp session: Bar is leader; zone on; source selected
        └─► Queue: House SyncGroup (if configured) or raw WiiM
                    ├─ WiiM (analog → amp → Bar / Kitchen / …)
                    └─ Sonys (digital sync with WiiM)
```

---

## Composer-style amp sessions

| You do this | What happens |
|---|---|
| Play on **Bar Speakers** | Bar becomes session **leader**; that zone turns on; queue goes to the playback target |
| **Group / members** → add Kitchen + Patio | Those zones turn on and join the session (`group_members` merges — does not replace) |
| Volume on Kitchen | Kitchen zone volume only |
| Remove / power off Patio | Patio leaves; queue keeps playing if other rooms remain |
| **Stop** on a facade | Stops (or pauses) the **playback** target (whole queue, including Sonys if House) |

**Do not** put amp facades in a Music Assistant SyncGroup with each other. They share an analog feed; use HA **group / members** (join) instead.

---

## Features

- Composer-style sessions via HA `media_player.join` / `unjoin` and `group_members`
- Shared queue on decoder or optional SyncGroup playback target
- Optional `select_source` when a zone turns on (exact name from the zone `source_list`)
- Per-zone volume; leaving a room does not stop the queue for others
- Zone picker: Control4 Audio **speaker** zones, plus matrix zones from Monoprice, Russound, Yamaha, Onkyo, Denon, etc.
- Services to turn all zones on/off for an entry
- Diagnostics download + repair if the configured source is missing from every zone `source_list`
- UI config (no YAML)

---

## Requirements

| Need | Example |
|---|---|
| Home Assistant | **2025.12** or newer |
| Music Assistant | With **Home Assistant Media Players** provider (typical use) |
| Decoder | WiiM Pro (or Cast / DLNA / LinkPlay / similar) that can `play_media` a URL |
| Amp zones | [Control4 Audio](https://github.com/heatvent/ha-c4-audio) speaker zones, or other supported matrix zone players |

Amp UDP / chassis control stays in [ha-c4-audio](https://github.com/heatvent/ha-c4-audio) (or your amp integration).

---

## Install (HACS)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Repository: `https://github.com/heatvent/ha-amp-zone-player`
3. Category: **Integration**
4. Download **Music Assistant Amp Zone Player**
5. **Restart** Home Assistant
6. **Settings → Devices & Services → Add Integration → Music Assistant Amp Zone Player**

HACS tracks **GitHub Releases** only (`hide_default_branch`). After a release, use **⋮ → Update information** if the update is slow to appear.

Custom-integration icons may show as “icon not available” in the HACS list until HACS picks up local brand assets; the icon still appears under **Settings → Devices & services** on HA 2026.3+.

### Manual

Copy `custom_components/amp_zone_player` into `config/custom_components/`, restart, then add the integration.

---

## Setup

1. **Decoder** — WiiM (analog out → amp input)
2. **Zones** — amp/matrix room players (Control4 Audio names must include “Speakers”; bare Amp/Switch players are hidden)
3. **Queue / SyncGroup player (optional)** — e.g. MA `House` / `Theater Speakers` SyncGroup entity in HA. Leave empty to send play directly to the decoder
4. **Amp input / source** — plain-text name from the zone source list (e.g. `WiiM Pro`), or **None**
5. **Name prefix** — usually blank
6. **Hub name** — optional (blank → `Amp zones`); does not prefix player names

Facade names look like `Bar Speakers`; entity ids like `media_player.bar_speakers` when free.

Reconfigure anytime: integration → **Configure** (refreshes unique id if decoder/zones change).

---

## Music Assistant

### Amp rooms only

1. Player providers → **Home Assistant Media Players** → enable the **facades** only  
2. Hide/uncheck the raw WiiM and the raw amp zone entities (do not disable the WiiM entity in HA — facades still need it)  
3. Select a facade → play → use **group / members** to add other facades  
4. Do **not** put amp facades in a SyncGroup with each other  
5. If audio cuts out mid-stream, try the facade’s **HTTP Profile** in MA player settings  

### WiiM + Sony (or other) SyncGroups

Use when digitally synced speakers (e.g. theater/basement AVRs) should play with the WiiM while amp ceilings ride the WiiM analog out.

1. In MA: **Settings → Players → Add group player** → **native Sync Group** (not Universal)  
2. Create one or more groups that all include the **WiiM**, for example:  
   - `Theater Speakers` = WiiM + basement Sony  
   - `Living Room Speakers` = WiiM + living-room Sony  
   - `Theater / Living Room` = WiiM + both Sonys  
3. Play **one** of those groups at a time (shared WiiM)  
4. On each Sony: **Stereo / Direct** (or Pure Direct); tune **Static playback delay** if a room echoes  
5. Hide the raw WiiM and Sonys in the MA UI if you only want the SyncGroups + facades visible (**Hide**, do not disable)  
6. Expose the SyncGroup(s) you care about to Home Assistant  
7. Optional: Amp Zone Player → **Configure** → **Queue / SyncGroup player** = your default group (e.g. `media_player.house`)  

**Day-to-day**

| Goal | Do this |
|---|---|
| Amp rooms only | Play a facade; join other facades. Leave SyncGroups / Sonys off. |
| Sonys + optional amp | Play the SyncGroup. Turn on / join the facades you want (source = WiiM). |
| New track from a facade with playback set | Play on the facade — queue goes to the SyncGroup; Sonys stay in sync. |

Do **not** press Play on a facade *and* on the SyncGroup for the same listen if that would double-drive the WiiM. With **Queue / SyncGroup player** set, facade Play is enough.

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
| **Play / play_media** | Facade becomes leader; zone on; queue on **playback** target (SyncGroup if set, else decoder). If that exact item is already playing, the zone only attaches (no second `play_media`). |
| **Join** | Member zones on; listed in `group_members` (merge) |
| **Unjoin / Off** | That zone off; leaves session; queue keeps playing if others remain |
| **Stop** | Stops (or pauses) the **playback** target |
| **Volume / Mute** | That zone only |
| **Pause / Next / Seek** | Playback target (shared) |

---

## Services

| Service | Effect |
|---|---|
| `amp_zone_player.turn_all_zones_on` | Power on every facade for a config entry (selects configured source when set) |
| `amp_zone_player.turn_all_zones_off` | Power off every facade; does not stop the decoder / SyncGroup queue |

Both take `config_entry_id` (pick the Amp Zone Player hub in the UI).

---

## Diagnostics & repairs

- **Download diagnostics** on the integration entry: decoder, playback target, zones, source lists, session membership  
- If the configured amp source is missing from every zone `source_list`, a **Repair** offers to clear it  

---

## Limits

- One analog feed — all joined amp rooms hear the same decoder stream  
- Amp facades are not digital sync members — SyncGroups are for WiiM + network players only  
- This integration only proxies HA entities; the amp integration must already work  
- Amp source spelling must match the zone `source_list` exactly when set  

---

## Troubleshooting

| Symptom | Check |
|---|---|
| No music | Decoder / SyncGroup can play a URL in HA; logs show `play_media → …`; amp source spelling |
| Third room replaces second | Need **0.2.2+** (join merges members) |
| Zones on, still silence | WiiM playing? Correct amp input? Zone volume > 0? |
| Mid-stream dropouts | MA player **HTTP Profile** on the facade |
| Echo vs Sonys | SyncGroup members only; Stereo/Direct on AVR; Static playback delay |
| HACS shows “icon not available” | Known HACS gap for local brands; check Devices & services for the icon |

---

## Support

- Repository: [github.com/heatvent/ha-amp-zone-player](https://github.com/heatvent/ha-amp-zone-player)
- Issues: [github.com/heatvent/ha-amp-zone-player/issues](https://github.com/heatvent/ha-amp-zone-player/issues)
- Amp / switch UDP: [ha-c4-audio](https://github.com/heatvent/ha-c4-audio)

## Credits

Developed with [Cursor](https://cursor.com).

## License

[MIT](LICENSE)

---

## Developers — releasing

HACS uses `manifest.json` `"version"` + a matching GitHub Release tag (`v1.1.1` ↔ `"1.1.1"`).

```powershell
.\tools\release.ps1 1.1.2 -Notes "Short summary for the release"
```
