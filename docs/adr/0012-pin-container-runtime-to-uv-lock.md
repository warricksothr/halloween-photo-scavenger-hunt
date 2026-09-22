# 0012. Pin the container runtime to uv.lock

Date: 2026-09-22
Status: accepted

## Context

The `Containerfile` installed the server with `pip install -e ./server`. That
resolves the lower-bound ranges in `pyproject.toml` and ignores `uv.lock`, so
the artifact that runs the party was the one thing not pinned while CI tested
the locked set. Pillow behavior is load-bearing (re-encode, dimensions, pHash),
so a version drift between CI and the image is a real defect, not a
formality.

## Decision

Commit `server/requirements.lock`, the export of `uv.lock`:

```
uv export --project server --locked --no-dev --no-emit-project
```

The image installs it with `pip install --no-cache-dir --require-hashes -r
./server/requirements.lock`, which pins every artifact by sha256, and does not
install the project as a distribution. Instead `ENV PYTHONPATH=/srv/arkham/server`
puts `app` on the import path from the source tree, which preserves the
`__file__`-relative data/static paths (see the layout note in the Containerfile).
A test regenerates the export and fails CI when the committed file drifts.

`PYTHONPATH` over an editable install is deliberate: Python 3.12 dropped
`setuptools` from `ensurepip`, so `pip install -e` runs PEP 517 build isolation
and fetches an unpinned `setuptools` — exactly the gap this change closes.
`--no-build-isolation` would need `setuptools` present, which means pinning a
build tool the app never imports. Skipping the build is simpler and leaves
nothing to pin.

## Consequences

The image and CI resolve identical versions, and every runtime artifact is
pinned by checksum. Adding or upgrading a dependency now means regenerating
`server/requirements.lock`; the guard test makes the omission a red build
rather than a silent drift. `app` is no longer an installed distribution, so a
tool that reads its package metadata (none does today) would have to be reached
through `PYTHONPATH`.
