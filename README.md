# Matrix Amplifier Zone Player

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/heatvent/ha-amp-zone-player)](https://github.com/heatvent/ha-amp-zone-player/releases)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg)](https://www.home-assistant.io/)

Bring **matrix amplifier zones** into Music Assistant as real players — without pretending the amp can decode audio.

A streamer (WiiM, Chromecast, etc.) stays the only device that plays music. Each amp zone becomes a facade `media_player` that Music Assistant can select, volume, and group. Power and volume go to the zone; transport, artwork, and queues go to the decoder.

---

## How it works

```text
Music Assistant
      │
      ▼
┌─────────────────────────────┐
│  Zone facades (this integ.) │  Kitchen · Patio · Theater · …
└─────────────┬───────────────┘
       ┌──────┴──────┐
       ▼             ▼
  Amp zones      Decoder
  on / off       play / pause
  volume         next / art
  mute           play_media
```

| You do this | It goes here |
|---|---|
| On / off / volume / mute | Zone `media_player` (e.g. [Control4 Audio](https://github.com/heatvent/ha-c4-audio)) |
| Play / pause / next / seek / browse / art | Decoder `media_player` (e.g. WiiM Pro) |

One decoder, one queue — many rooms on the same stream. That matches how a matrix amp is wired.

---

## Features

- One Home Assistant / Music Assistant player per amp zone
- Shared decoder for playback, metadata, and `play_media`
- Optional `select_source` when a zone turns on (route to the jack your streamer uses)
- Turning a zone **off** does not stop the decoder while other facade zones are still on
- Works with any zone entities that support power + volume — not Control4-specific
- Configure and change options from the UI (no YAML)

---

## Requirements

| Need | Example |
|---|---|
| Home Assistant | 2024.12 or newer |
| Decoder | WiiM Pro, or any `media_player` that can play media |
| Amp zones | Zone `media_player`s with on/off + volume (e.g. `c4_audio` zones) |

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

1. **Decoder** — the real streamer Music Assistant should drive for content
2. **Zones** — one or more amp zone `media_player` entities
3. **Amp input / source** — pick from the dropdown built from each zone’s **source list** (same plain-text labels as the zone Source control, e.g. `WiiM Pro`). This is **not** an entity. Choose **None** to skip auto-routing, or type the exact label if it is missing from the list.
4. **Name prefix** *(optional)* — prefix for facade entity names

Then in **Music Assistant**:

- Enable the new facade players
- Disable or hide the raw decoder so you do not get two targets for one streamer
- Group facades when you want whole-home on the same stream

---

## Behavior

| Action | Result |
|---|---|
| **Turn on / Play** | Zone on → optional source select → play on decoder |
| **Volume / Mute** | Zone only |
| **Pause / Next / Previous / Seek** | Decoder |
| **Stop** | That zone off (decoder keeps running if other zones are on) |
| **Off** | Zone off; decoder left alone if another facade zone is still on |

---

## Limits

- **One queue.** Kitchen and Patio cannot play different tracks through this bridge — they share the decoder.
- **Not multi-room sync hardware.** Groups mean “several rooms hearing the same analog feed,” not Sonos-style independent players.
- **Amp still needs a zone integration.** This package does not speak amplifier UDP; pair it with something like [ha-c4-audio](https://github.com/heatvent/ha-c4-audio) for the chassis.

---

## Support

- Issues: [github.com/heatvent/ha-amp-zone-player/issues](https://github.com/heatvent/ha-amp-zone-player/issues)
- Amp / switch UDP control: [ha-c4-audio](https://github.com/heatvent/ha-c4-audio)

---

## Developers — releasing

From a clean `main`:

```powershell
.\tools\release.ps1 0.1.2 -Notes "Short summary for the release"
```

Bumps `manifest.json`, updates the changelog, tags `vX.Y.Z`, and publishes the GitHub Release HACS reads. Tag and `manifest.json` `"version"` must match.
