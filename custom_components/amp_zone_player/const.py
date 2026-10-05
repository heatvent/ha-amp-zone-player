"""Constants for Music Assistant Amp Zone Player."""

DOMAIN = "amp_zone_player"
PLATFORMS = ["media_player"]

CONF_DECODER = "decoder"
CONF_ZONES = "zones"
# MA / AirPlay / Cast players (e.g. Sony AVRs) that join the decoder digitally.
CONF_DIGITAL_ZONES = "digital_zones"
# Optional sound mode applied when a digital zone joins (exact AVR/MA string).
CONF_DIGITAL_SOUND_MODE = "digital_sound_mode"
CONF_SOURCE = "source"
CONF_NAME_PREFIX = "name_prefix"
# Optional MA SyncGroup (or other player) that owns the queue when Sonys join.
CONF_PLAYBACK = "playback"

DEFAULT_NAME_PREFIX = ""

ZONE_KIND_AMP = "amp"
ZONE_KIND_DIGITAL = "digital"
