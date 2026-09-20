# Changelog



## 0.2.9 - 2026-09-20

- Polish: source None sentinel, options unique_id refresh, soft-fail rename, typed DeviceInfo; README matches speaker-zone picker.

## 0.2.8 - 2026-09-20

- Zone picker hides bare Control4 Amp / Switch players; only speaker zones (e.g. Bar Speakers) are listed.

## 0.2.7 - 2026-09-20

- Fix invalid trailing commas in translations that blocked the integration from loading after setup.

## 0.2.6 - 2026-09-20

- Zone picker whitelists Control4 Audio only (one media_player per amp zone); decoder picker limited to streamers like WiiM.

## 0.2.5 - 2026-09-20

- Zone picker hides Music Assistant, Alexa, and facade entities so only real amp zones appear.

## 0.2.4 - 2026-09-20

- Harden playback and grouping: safe service calls, stopÃ¢â€ â€™pause fallback, source select soft-fail, join skips failed zones.
- Only advertise SEEK among decoder passthrough features (no browse/shuffle without handlers).
- README behavior table matches code (Stop vs Unjoin); troubleshooting section added.
- Prevent duplicate config entries for the same decoder+zones set.

## 0.2.3 - 2026-09-20

- Fix no-audio: wake WiiM and play URLs without Cast extra metadata; media_stop stops the decoder instead of leaving the room.

## 0.2.2 - 2026-09-20

- Fix grouping: joining a third zone adds it instead of replacing the second.

## 0.2.1 - 2026-09-20

- Rename to Music Assistant Amp Zone Player; README documents Composer-style MA sessions.

## 0.2.0 - 2026-09-20

- Composer-style sessions: play from one room, join other zones, per-zone volume (HA GROUPING for Music Assistant).

## 0.1.9 - 2026-09-20

- README clarifies this wraps zone + decoder entities; Music Assistant is a common use, not the only one.

## 0.1.8 - 2026-09-20

- Entity ids are bar_speakers (no mazp_ prefix). Facades wrap zone + decoder media players.

## 0.1.7 - 2026-09-20

- Facade names are Bar Speakers (not bare area names like Bar).

## 0.1.6 - 2026-09-20

- Short names (Bar Speakers) and mazp_* entity ids; hub name optional and never prefixes players.

## 0.1.5 - 2026-09-20

- GitHub link in README; short player names only (no Control4/device prefixes).

## 0.1.4 - 2026-09-20

- Auto-shorten player names (area or strip Control4 Amp prefix); no manual rename needed.

## 0.1.3 - 2026-09-20

- Fix: show as Integration (hub) not Helper; nest zone facades under the device.

## 0.1.2 - 2026-09-20

- Source step: pick amp input from zone source list (plain text), or type it; clarified this is not an entity.

## 0.1.1 - 2026-09-20

- Rename to Matrix Amplifier Zone Player; polished HACS README.

## 0.1.0 - 2026-09-20

- Initial scaffold: config flow, zone facades, decoder proxy for Music Assistant.
