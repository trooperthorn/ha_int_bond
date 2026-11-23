# Decisions

Dated decisions with the alternative rejected and why.

## 2026-09-04, the flame number reports `UnitOfRatio.PERCENTAGE`

`PERCENTAGE` as a unit of measurement is deprecated since core 2026.7 (developer blog
2026-06-30). Rejected: keeping the bare constant until removal.

## 2026-09-04, `aiohttp.ClientResponseError` catches stay

The scanner flags every `ClientResponseError` catch because the OAuth2 helper now raises
its own subclasses (developer blog 2026-02-19). This integration talks to the Bond Local
API with a static token and never uses the OAuth2 helper, so those subclasses can never
appear; the catches handle real HTTP errors from the bridge. Rejected: catching
`OAuth2TokenRequestReauthError`, which would be dead code.

## 2026-09-04, the config flow keeps `async_update_reload_and_abort`

The scanner flags the three reload sites because combining them with a config entry
update listener becomes an error in core 2026.12 (developer blog 2026-05-07). This
integration registers no update listener, so the flow's reloads are the only reload path
and the rule does not apply. Rejected: switching to `async_update_and_abort`, which would
leave a host or token change unapplied until a manual reload.

## 2026-09-04, ruff joins the gate; mypy waits

Ruff with the house rule set (E, W, F, I, UP, B, SIM, C4, RUF; E501 and RUF012 ignored,
the latter because Home Assistant entity classes set `_attr_supported_color_modes` as a
class-level set by design) runs in CI. Rejected for now: mypy, which reports 29 errors in
five files that need individual review; see `backlog.md`.

## 2026-09-04, `Prepare release` compares versions without the tag prefix

The decision step compared the bare manifest version with the tagged name, so every run
concluded the version was already ahead and never opened a bump PR. The tag prefix is
stripped before the comparison. Rejected: dropping the `v` prefix from tags, which the
existing releases already carry.

## 2026-11-23, the test harness is `pytest-homeassistant`

`pytest-homeassistant-custom-component` stopped at 0.13.375, which pins core 2026.10.4, and
its README points to `pytest-homeassistant`, published from `home-assistant/core`. Core
2026.11 aliases httpx at import, which the old plugin cannot load under. The suite now
installs `pytest-homeassistant==2026.11.1`, imports `pytest_homeassistant`, and takes the
pytest settings from that package's README (`asyncio_default_fixture_loop_scope`,
`-p no:respx`, `pythonpath`). The wrapper fixture that requested
`enable_custom_integrations` is gone because `hass` enables custom integrations by default.
The harness pin, the core pin and the CI version literal name one version and move
together. Rejected: staying on core 2026.10 until the old harness caught up, which it will
not.
