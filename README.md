# Bond Pro for Home Assistant

A modernized rework of the Home Assistant [Bond](https://www.home-assistant.io/integrations/bond) integration, built and verified against a live Bond Bridge BD-1000 (fw v4.32.7). It targets — and in several areas exceeds — the requirements of the Home Assistant quality scale's Platinum tier (the core integration is unrated/grandfathered).

Runs alongside or instead of the core `bond` integration under its own domain, `bond_pro`.

## What it adds over the core integration

### Reliability
- **Reauth flow** — an invalidated token triggers Home Assistant's reauth UI instead of silently killing the entry (core returns `False` on a 401).
- **Reconfigure flow** — change host/token without deleting the entry.
- **Self-healing BPUP push** — the forked [`bond-async`](https://github.com/trooperthorn/bond-async) reconnects the UDP push channel with jittered backoff and sends keep-alives every 30 s (core's client never reconnects and keeps alive at exactly the bridge's 60 s session timeout).
- **One fallback poller per hub** — a single `DataUpdateCoordinator` sweeps device state (30 s while push is down, 5 min as a drift check) instead of one timer per entity (~20 timers on an 8-device bridge).
- **Per-request HTTP headers** — fixes a shared-mutable-header race in upstream `bond-async` that could mis-tag `BOND-UUID` message IDs across concurrent requests.

### New entities
| Entity | Source | Notes |
| --- | --- | --- |
| Wi-Fi signal (dBm) | `/v2/sys/wifi/sta` | Diagnostic sensor on the bridge device |
| Last restart | `uptime_s` | Timestamp sensor, detects bridge reboots |
| RF frequency per device | device properties | Diagnostic, disabled by default; carries `bps`, `zero_gap` attributes |
| Blue light | `/v2/bridge` `bluelight` | The bridge's ring light as a dimmable light (config category) |
| Flame | `SetFlame` | Number entity (0-100 %) for fireplaces |
| Faults | `/v2/sys/faults` | Problem binary sensor (`faults`, `raise_count` attributes); only created when the bridge supports fault reporting |
| Clear faults | `PATCH /v2/sys/faults` | Config button on the bridge; clears faults that need a manual clear |
| Pair / Unpair / Unpair from all appliances | `Pair`, `Unpair`, `UnpairSelf` | Config buttons, disabled by default, on devices that expose those actions. Without `Unpair`, `Pair` toggles |

### New actions (services)
- `bond_pro.rf_scan` — returns the bridge's RF noise scan (`freq_khz`/`rssi` pairs across all supported bands) as response data. Useful for diagnosing flaky RF devices.
- `bond_pro.transmit_command` — transmits a stored command's raw RF signal directly.
- The core tracked-state services (`set_fan_speed_tracked_state`, `set_switch_power_tracked_state`, `set_light_power_tracked_state`, `set_light_brightness_tracked_state`) are kept as-is. The deprecated light services (`start_increasing_brightness`, `start_decreasing_brightness`, `stop`) are dropped — the equivalent buttons remain.

### Modernization
- `has_entity_name` naming, entity translations, icon translations.
- `ConfigEntryAuthFailed` / `ConfigEntryNotReady` semantics, `PARALLEL_UPDATES`, typed `runtime_data`.
- Diagnostics with token/network/RF-address redaction plus a live Wi-Fi + RF-scan snapshot.
- `quality_scale.yaml` tracking every rule.

## Installation

### HACS (custom repository)
1. HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/trooperthorn/ha_int_bond` as type *Integration*.
2. Install **Bond Pro**, restart Home Assistant.
3. Settings → Devices & Services → Add integration → **Bond Pro**. Bridges on the LAN are also discovered automatically (DHCP/zeroconf).

### Token
The local token is in the Bond app under your bridge → Settings → *Local API*, or is fetched automatically if the bridge was power-cycled in the last 10 minutes (the config flow tries this first).

### Manual
Copy `custom_components/bond_pro` into your `config/custom_components/`. No pip requirements: the forked `bond-async` library is vendored inside the component as `bond_async_pro` (the Home Assistant container ships upstream `bond-async==0.2.1` for the core integration, which would otherwise shadow the fork and break setup with `'Bond' object has no attribute 'wifi_sta'`). The fork's source of truth is [trooperthorn/bond-async@pro](https://github.com/trooperthorn/bond-async/tree/pro); re-vendor by copying its `bond_async/` package over `custom_components/bond_pro/bond_async_pro/`.

## Blueprints

Import from `blueprints/automation/bond_pro/`:

- **Storm guard** — weather turns stormy → fans off, covers closed, phone notified to shut windows.
- **Solar-aware comfort** — boost ceiling fans while solar production exceeds a threshold; settle back on deficit.
- **Seasonal fan direction** — forward in summer, reverse in winter (needs the Season integration).
- **Evening switch schedule** — sunset-to-time schedule for an RF outlet (e.g. holiday lights), date-window gated.

## Development

```bash
pip install pytest-homeassistant-custom-component==0.13.362
pip install -r requirements_test.txt
pytest
```

The test suite (22 tests) runs on Linux and native Windows; `tests/conftest.py` documents the Windows socket/event-loop workarounds.

See [docs/README.md](docs/README.md) for protocol- and wire-level facts behind the code.

## Deferred features

Documented in the [Bond Local API](https://docs-local.appbond.com/) but deliberately not implemented yet. The same list is in `DEFERRED_FEATURES` in `const.py` and under `deferred_features` in diagnostics.

| Feature | API |
| --- | --- |
| Groups | `/v2/groups` (library calls exist, no platform) |
| Scenes | `/v2/scenes`, `PUT /v2/scenes/{id}/run` |
| Schedules | `/v2/{devices,groups,scenes}/{id}/skeds` |
| Reboot button | `PUT /v2/sys/reboot` (library call exists) |
| Identify button | `/v2/sys/indicate` |
| Power / vitals diagnostics | `/v2/sys/power`, `/v2/sys/vitals` (Mate Pro, v4.28+) |
| Ethernet diagnostics | `/v2/sys/eth` |
| Device reload | `PUT /v2/devices/{id}/reload` |
| Channels | `/v2/channels` (Mate) |
| BPUP broadcast option | `PATCH /v2/api/bpup` |
| Shade tilt | `ToggleTilt`, `SetTiltPosition` |
| Top-down/bottom-up shades | upper/lower rail actions |
| Sheer/blackout shades | `SetSheerPosition`, `SetBlackoutPosition` |
| Raise/Lower-only shades | `Raise`, `Lower`, `Retract`, `Extend` |
| Heat | `SetHeat`, `IncreaseHeat`, `DecreaseHeat`, `HeatPresetNext`/`Prev` |

## Known limitations

- Devices added to the bridge after setup appear after a reload of the config entry.
- The firmware **update entity** is not implemented yet: `/v2/sys/upgrade` reports upgrade *status* but the availability check goes through Bond's cloud; needs further protocol work.
- Sidekick remote **event entities** are planned; the library fork already exposes `/v2/sidekicks`.
- `strict-typing` (Platinum) is pending typed models in the library fork.

## Credits

Based on the Home Assistant core `bond` integration (Apache-2.0) by @bdraco, @prystupa, @joshs85, @marciogranzotto, and on Olibra's `bond-async` (MIT). See NOTICE.md.
