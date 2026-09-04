# Backlog

Dated open items.

- 2026-09-04: `mypy --ignore-missing-imports --follow-imports=skip
  custom_components/bond_pro` reports 29 errors in five files, including a real
  type mismatch in `button.py` (`mutually_exclusive` given a string where an
  `Action` is expected). Review each, then add mypy to the Test workflow.
- 2026-09-04: install the release GitHub App on this repository and set
  `RELEASE_AUTOMATION_CLIENT_ID` and `RELEASE_AUTOMATION_PRIVATE_KEY`; until then
  version bumps are manual (see `operations.md`).
- 2026-09-04: list the brand in `home-assistant/brands` so the HACS brands check can
  be re-enabled in `validate.yml`.
- 2026-09-04: three Dependabot PRs (CodeQL init and analyze pins, aioresponses floor)
  are open and pass their checks; merge or close them deliberately.
