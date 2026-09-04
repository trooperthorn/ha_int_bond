# Operations

The test gate and the release path. Wire-level facts live in `protocol.md`.

## Test gate

The gate is the same on a workstation and in CI: `ruff check custom_components tests
scripts`, `pytest tests/ -q`, then `python scripts/build_release_artifacts.py
--validate-only`.

Pins live in `requirements_test.txt` and `requirements_core.txt`. The Home Assistant test
harness (`pytest-homeassistant-custom-component`) pins the beta core it was cut from, and
pip refuses to resolve a different core in the same install, so the stable `homeassistant`
pin lives in its own file and is installed second. The CI job asserts the installed core
version so a harness bump that silently moves the core is caught. The harness imports
`fcntl`, so on Windows the suite runs under WSL.

`mypy` is not in the gate yet; see `backlog.md`.

## Release path

A merge to `main` is the only release path. Nobody edits the manifest version or pushes a
tag by hand.

1. `Release` runs on every push to `main`. It calls the Test and Validate workflows, then
   reads the version from `custom_components/bond_pro/manifest.json` through
   `.release.json`. If a published release for that version already exists it stops.
   Otherwise it creates the `v<version>` tag on the exact commit, drafts a release with
   generated notes, and publishes it. HACS installs the tagged tree, so no archive is
   attached.
2. `Prepare release` runs after every successful `Release` on `main`. When the manifest
   version equals the latest published release and `custom_components/bond_pro` changed
   since that tag, it runs `scripts/set_version.py --next-from-tags`, pushes the bump to
   `automation/calver-release` with a GitHub App token, opens a PR, and arms squash
   auto-merge. The merge triggers `Release` again, which publishes the new version. Docs,
   tests, and workflow changes do not bump the version.
3. Without the GitHub App credentials the second step fails at its credential check and
   nothing else happens. The repository still releases: run
   `python scripts/set_version.py --next-from-tags` on a branch, open the PR, and the
   merge publishes.

`.release.json` is the single statement of what ships: the tag prefix (`v`), the time zone
the CalVer date is taken in, the release-bearing path, and the version field.
`scripts/set_version.py` is the only writer of that field; `scripts/release_config.py`
behind `build_release_artifacts.py --validate-only` is the independent reader, so a writer
defect cannot validate itself. Versions are `YYYY.MM.DD.N` in `America/Chicago`.

### GitHub App for zero-touch version PRs

`Prepare release` needs the release GitHub App (Contents: Read and write, Pull requests:
Read and write) installed on this repository, plus the repository variable
`RELEASE_AUTOMATION_CLIENT_ID` and the Actions secret `RELEASE_AUTOMATION_PRIVATE_KEY`.
The same App serves every trooperthorn Home Assistant repository; each repository holds
its own copy of the variable and secret. The token is minted only after the workflow has
proved a bump is needed, expires on its own, and is scoped to this repository. The
workflow's own `GITHUB_TOKEN` stays read-only.

### Branch and protection settings

`main` is the only long-lived branch. Work happens on short-lived branches that end in a
squash-merged PR and are deleted on merge. Branch protection requires the job display
names `pytest (Python 3.14)`, `HACS validation`, `hassfest (manifest sanity)`,
`CodeQL (python)`, and `Python static security checks`, with strict up-to-date checks,
enforced for administrators, no force pushes, no deletions, and no required approvals.

### HACS brands check

This repository is not listed in `home-assistant/brands`, so the HACS action runs with
that check ignored. Listing the brand upstream would let the ignore be removed.

## Line endings

`.gitattributes` pins every text file to LF so Windows checkouts and WSL or Linux tools
see the same bytes.
