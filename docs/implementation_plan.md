# Implementation Plan

## Phase 1: Foundation
- Add `pyproject.toml` and create the `automation/` Python package.
- Implement CLI entrypoints for `backfill`, `sync`, `render`, `validate`, and `plan`.
- Add Google Drive auth and discovery support.

Acceptance criteria:
- `python -m automation.cli courses plan` runs against repo data.
- `python -m automation.cli courses validate` reports schema and freshness issues clearly.

## Phase 2: Structured Teaching Data
- Create `data/teaching/courses.yml`.
- Create `data/teaching/materials/<slug>.yml` files.
- Migrate existing teaching content into normalized YAML records.

Acceptance criteria:
- Legacy teaching content exists in repo-managed data files.
- Each published course page maps to one canonical course record.

## Phase 3: Rendering And Validation
- Generate `teaching/<slug>.md` from templates and normalized data.
- Replace the dynamic portion of `teaching.md` through explicit managed markers.
- Add validator checks for duplicate slugs, broken generated state, and supported URL patterns.

Acceptance criteria:
- `courses render` reproduces all teaching pages deterministically.
- `courses validate` passes on a clean checkout after rendering.

## Phase 4: Docs, Tests, CI, And PR Flow
- Add internal docs under `docs/`.
- Add unit and integration-style tests under `tests/`.
- Add a GitHub Actions workflow that runs validation and `jekyll build`.
- Support local commit/push/PR creation for completed sync runs.

Acceptance criteria:
- Local test suite passes.
- CI catches stale generated files and Jekyll build regressions.
- The repo contains a documented single-command path from backfill to PR.
