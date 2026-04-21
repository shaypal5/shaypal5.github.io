# Operations

## Environment Contract
Expected environment variables:
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_OAUTH_TOKEN_URI` optional, defaults to Google's standard token endpoint
- `GOOGLE_DRIVE_ROOTS` optional comma-separated parent folder IDs
- `GITHUB_REPO` optional override, defaults to `shaypal5/shaypal5.github.io`

`direnv` is the intended local injection mechanism for v1.

## Common Commands
```bash
python -m automation.cli courses plan
python -m automation.cli courses render
python -m automation.cli courses validate
python -m automation.cli courses backfill --dry-run
python -m automation.cli courses backfill --publish-pr
```

## PR Agent Context
- `CI` uploads raw `.coverage*` data, combines it into `coverage.xml`, and publishes both artifact outputs for downstream PR context analysis.
- `pr-agent-context` runs as part of `CI` on pull requests and uses `coverage-xml` to compute patch coverage commentary.
- `pr-agent-context-refresh` reruns on review and later check signals with `publish_mode: append`, reusing the latest `coverage-xml` artifact from the matching `CI` run when possible.
- `pr-agent-context-refresh` also has a repo-owned `schedule` -> `workflow_dispatch` fallback for same-repo PRs so approval-gated bot review events do not leave refresh stuck.
- Scheduled fallback refreshes pass explicit PR context overrides:
  - `pull_request_number`
  - `pull_request_base_sha`
  - `pull_request_head_sha`
- The scheduled dispatcher uses:
  - bounded recent comment lookup
  - recent/in-flight dispatch dedupe
  - per-PR error isolation
  - SHA-aware `workflow_dispatch` concurrency grouping

## Typical Backfill Flow
1. Export credentials through `direnv`.
2. Run `courses backfill --dry-run` to inspect the planned changes.
3. Review generated YAML and markdown output.
4. Run `courses validate`.
5. Run `courses backfill --publish-pr` when satisfied with the result.

## Common Failure Cases
- Exit code `2`: OAuth variables are missing or token refresh failed.
- Exit code `3`: Drive listing failed or returned an unexpected error.
- Exit code `1`: data is incomplete, generated files are stale, or a URL is invalid.
- Exit code `4`: git push or `gh pr create` failed.

## Repairing Partial Runs
- Re-run `courses render` after editing YAML or templates.
- Re-run `courses validate` before committing.
- If a sync partially succeeded, inspect `data/teaching/` and rerun `courses backfill --slug <slug>` for the affected course.
