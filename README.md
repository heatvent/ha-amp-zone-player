# Amp Zone Player for Home Assistant

Generic companion integration that exposes **amp zone facades** Music Assistant (and HA) can treat as players.

It does **not** speak amplifier UDP. It proxies:

| Action | Goes to |
|---|---|
| On / off / volume / mute | Zone `media_player` (e.g. Control4 Audio zone) |
| Play / pause / next / seek / `play_media` / art / metadata | Decoder `media_player` (e.g. WiiM Pro) |

One decoder feeds many rooms. Facades are **rooms on the same stream**, not independent queues.

## Requirements

- Home Assistant 2024.12+
- A decoder entity that can play media (WiiM, Chromecast, etc.)
- Zone entities that support turn on/off and volume (e.g. [`ha-c4-audio`](https://github.com/heatvent/ha-c4-audio) zones)

## Install (HACS)

1. HACS → Integrations → Custom repositories → this repo URL, category **Integration**.
2. Download **Amp Zone Player**, restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **Amp Zone Player**.

## Setup

1. Pick the **decoder** (real streamer).
2. Pick one or more **zone** media players.
3. Optional: **source name** to `select_source` on each zone when turning on (e.g. the amp input labeled `WiiM Pro`).
4. Optional: name prefix for the facade entities.

In Music Assistant, use the facade players and hide the raw decoder so you do not get two targets for one streamer.

## Behavior

- **Turn on / play** → turn zone on, optionally select source, unmute if needed, forward play to the decoder.
- **Volume / mute / off** → zone only.
- **Off** → turns that zone off; does **not** stop the decoder while any other facade zone in this entry is still on.
- **Transport / browse / artwork** → decoder.

## Limits

- One decoder → one queue. Kitchen and Patio cannot play different tracks through this bridge.
- MA groups of several facades = several rooms hearing the same decoder stream.
