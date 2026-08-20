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
