# Teaching Automation Project Overview

## Purpose
This internal project adds a local automation layer to the personal site repository so teaching content can be discovered from Google Drive, normalized into repo-managed data, rendered into public Jekyll pages, validated locally and in CI, and then proposed through a pull request.

## Goals
- Make teaching updates agent-driven and repeatable.
- Keep the published site under normal git review and PR workflows.
- Separate internal automation code and docs from deployed site content.
- Ensure generated teaching pages and the teaching index never drift apart.

## Non-goals
- Running the sync inside GitHub Actions.
- Turning Google Drive into the direct production source of truth.
- Mutating Drive folder structure or file permissions.
- Rebuilding the site on a new frontend framework.

## Current Constraints
- The site is a small Jekyll repository built from markdown pages.
- Teaching pages were previously hand-authored under `teaching/*.md`.
- Google credentials are expected locally through `direnv` environment variables.
- Local automation may later be invoked by Codex, a daemon, or `n8n`, but v1 keeps orchestration in this repo.

## Chosen Model
V1 keeps structured YAML in `data/teaching/` as the canonical repo-side source of truth:
- `courses.yml` stores normalized course records.
- `materials/<slug>.yml` stores per-course material lists.
- `automation/` renders markdown pages from the data.

This keeps manual review easy, supports deterministic validation, and gives agents a stable place to record overrides and notes.

## V1 Workflow
1. Discover Google Drive folders whose names end with ` CF`.
2. Infer initial course metadata and extract public material candidates.
3. Persist normalized records in YAML.
4. Render `teaching/<slug>.md` and the managed block in `teaching.md`.
5. Run repository validation and a Jekyll build.
6. Create a branch, commit, push, and open a PR for review.
