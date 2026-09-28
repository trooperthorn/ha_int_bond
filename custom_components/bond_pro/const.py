"""Constants for the Bond Pro integration."""

from datetime import timedelta

BRIDGE_MAKE = "Olibra"

DOMAIN = "bond_pro"

CONF_BOND_ID: str = "bond_id"

# Fallback polling of device state.  BPUP push is the primary state source;
# the coordinator only sweeps this often when push is down, and slowly as a
# drift check while push is healthy.
FALLBACK_INTERVAL_BPUP_DEAD = timedelta(seconds=30)
FALLBACK_INTERVAL_BPUP_ALIVE = timedelta(minutes=5)

# Bridge telemetry (Wi-Fi RSSI, uptime, blue light) polling.
TELEMETRY_INTERVAL = timedelta(seconds=60)

# Bond Local API features (https://docs-local.appbond.com/) that are
# deliberately not implemented yet. Surfaced in diagnostics and the README
# so the gap against the documented API stays visible.
DEFERRED_FEATURES: dict[str, str] = {
    "groups": "/v2/groups: group entities (library calls exist, no platform)",
    "scenes": "/v2/scenes: scene entities, PUT /v2/scenes/{id}/run",
    "skeds": "/v2/{devices,groups,scenes}/{id}/skeds: schedule management",
    "reboot": "PUT /v2/sys/reboot: restart button (library call exists)",
    "indicate": "/v2/sys/indicate: identify button",
    "power": "GET /v2/sys/power: power supply diagnostics",
    "vitals": "GET /v2/sys/vitals: Mate Pro (MT-1500) diagnostics, v4.28+",
    "device_reload": "PUT /v2/devices/{id}/reload",
    "eth": "GET /v2/sys/eth: Ethernet diagnostics",
    "channels": "/v2/channels: Mate multi-channel products",
    "bpup_broadcast": "PATCH /v2/api/bpup broadcast option",
    "shade_tilt": "ToggleTilt, SetTiltPosition cover tilt",
    "shade_tdbu": "Upper/lower rail actions for top-down/bottom-up shades",
    "shade_sheer_blackout": "SetSheerPosition, SetBlackoutPosition",
    "shade_raise_lower": "Raise, Lower, Retract, Extend for shades without Open/Close",
    "heat": "SetHeat, IncreaseHeat, DecreaseHeat, HeatPresetNext/Prev",
}
