# Releasing

Insight Orchestra uses [release-please](https://github.com/googleapis/release-please)
to cut releases from Conventional Commits, and publishes prebuilt Docker images
to GHCR when a tag is created.

## The flow

1. **Merge PRs to `main` with Conventional Commit titles** (`feat:`, `fix:`,
   `chore:`, …). `pre-commit` enforces the format locally, and it matters on the
   **PR title** because PRs are squash-merged.
2. **release-please keeps a `chore(main): release X.Y.Z` PR open.** It bumps the
   version in `pyproject.toml` and `frontend/package.json`, updates
   `.release-please-manifest.json`, and writes the `CHANGELOG.md` entry.
3. **Merge that release PR.** release-please then creates the `vX.Y.Z` tag and
   the GitHub Release.
4. **Images publish.** A `GITHUB_TOKEN`-pushed tag does not trigger workflows,
   so `release-please.yml` explicitly dispatches `publish-images.yml` against
   the new tag. That builds `linux/amd64` + `linux/arm64`, stitches the digests
   into one manifest per component, and applies the tags below.

## Versioning

- **One version for the whole app** (backend + frontend) — it's a self-hosted
  product, not a library. `feat:` → minor, `fix:` → patch, `!` / `BREAKING
  CHANGE` → major.
- **`latest`** tracks the newest stable release; prereleases never get it.
- **`edge`** is a nightly build of the tip of `main` (no `latest`/semver tags)
  for testers — published by `publish-images.yml` on its schedule.
- Images carry a **`X.Y.Z`**, **`X.Y`**, and **`X`** tag in addition to `latest`,
  so `IO_IMAGE_TAG=v1.1.0` (or `=1.1`) pins reproducibly.

## What a running instance reports

`GET /health` returns `{"status":"ok","version":"X.Y.Z"}`. Released images bake
the tag in at build time (`IO_VERSION`); a from-source build reports `dev`.

## Pinning

`docker-compose.yml` defaults to `latest`. To pin a release:

```bash
IO_IMAGE_TAG=v1.1.0 docker compose up -d
```

## Housekeeping

`cleanup-images.yml` trims each GHCR package to its most recent versions on a
monthly schedule, so storage doesn't grow without bound.
