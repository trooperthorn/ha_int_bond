# Bond Local API and BPUP protocol facts

Verified against a live Bond Bridge BD-1000 (fw v4.32.7) unless marked
unverified.

## BPUP keep-alive interval

The bridge expires a BPUP session 60 seconds after the last keep-alive. The
integration sends a keep-alive every 30 seconds (`BPUP_KEEP_ALIVE_INTERVAL`
in `bond_async_pro/bpup.py`) so a single lost datagram does not silently drop
push updates until the next interval. The upstream `bond-async` library sends
every 60 seconds, equal to the timeout, so one lost packet there causes a
silent gap until the following keep-alive.

## Action step size on tracked-state and dimmer actions

The `/v2/devices/{id}/actions/{action}` endpoint for `StartIncreasingBrightness`
/ `StartDecreasingBrightness` and similar step actions requires a step-size
argument, but it does not appear to affect the underlying device: it is
assumed to just gate an increase/decrease signal. `STEP_SIZE` in
`button.py` is set to `10` as an arbitrary non-zero value. Unverified beyond
observed behavior on the BD-1000; if a future device model is found to honor
the value, revisit.
