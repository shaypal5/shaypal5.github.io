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

## Ruby And Jekyll
Use Ruby 3.3.0 for local Jekyll builds. The repo includes `.ruby-version`
for rbenv-compatible tooling, and the checked-in `Gemfile.lock` currently
expects Bundler 2.7.2.

```bash
RBENV_VERSION=3.3.0 bundle install
RBENV_VERSION=3.3.0 bundle exec jekyll build
```

Plain `bundle exec jekyll build` may use macOS system Ruby instead, which can
fail before Jekyll starts if Bundler 2.7.2 is not installed for that Ruby.

## Redirects
Redirects use the GitHub Pages-supported `jekyll-redirect-from` plugin. See
`docs/redirects.md` before renaming any public page or adding URL aliases.

## SEO Metadata
Common SEO, OpenGraph, Twitter card, canonical URL, and Person JSON-LD metadata
is emitted by `_includes/seo.html` through the shared head include.

Keep stable identity fields in `_config.yml`, especially `url`, `social_image`,
`author.url`, `author.job_title`, and the profile handles under `author`. The
Person JSON-LD `sameAs` list is derived from `author.github`,
`author.linkedin`, and `author.twitter`; use `author.same_as_extra` only for
additional profile URLs that cannot be derived from those handles. Page
descriptions should stay in page front matter; for generated archive pages, edit
the matching `data/*.yml` `front_matter.description` value instead of the
generated Markdown.

Optional page front matter:
- `image`: page-specific social preview image. Relative paths are expanded to
  absolute URLs.
- `og_type`: page-specific OpenGraph type. Defaults to `website`.

## External Link Attributes
Links that open a new tab must include Kramdown attributes for both the tab
target and opener hardening:

```markdown
[Example](https://example.com){:target="_blank" rel="noopener noreferrer"}
```

The renderer emits those attributes for generated course links and hardens
blank-target Kramdown links in generated public pages. Validation fails if
authored or generated public Markdown adds a blank-target link without
`rel="noopener noreferrer"`.

## Common Commands
```bash
python -m automation.cli courses plan
python -m automation.cli courses render
python -m automation.cli courses validate
python -m automation.cli courses backfill --dry-run
python -m automation.cli courses backfill --publish-pr
RBENV_VERSION=3.3.0 bundle exec jekyll build
python -m automation.cli courses check-links
```

## External Link Checks
`courses check-links` scans rendered `_site/**/*.html` for external `href`, `src`, selected SEO metadata image/canonical URL fields, and HTTP(S) URL strings in JSON-LD by default. Build the site first, then run the checker:

```bash
RBENV_VERSION=3.3.0 bundle exec jekyll build
python -m automation.cli courses check-links
```

Use `--source source` when you specifically want to scan public Markdown pages, generated teaching pages, public-page YAML data, and teaching YAML data before rendering. The checker de-duplicates URLs before checking them and reports the first source or rendered HTML location for each failure.

The checker uses `automation/external_link_allowlist.yml` by default. Add a rule there when a domain or URL is intentionally excluded from automated checks, for example because the provider blocks CI, rate-limits headless probes, or requires auth while the public link remains intentionally published. Supported `match` values are `domain`, `prefix`, `exact`, and `regex`; every entry must include a `reason`.

The checker treats HTTP `401`, `403`, and `429` as soft successes because those responses usually mean the URL exists but the remote service requires auth or throttled the probe. Other `4xx` responses fail the command after a GET fallback. Use `--timeout`, `--retries`, `--workers`, `--source`, `--site-root`, and `--allowlist` to tune one-off runs.

`External Link Check` runs the default rendered-site command through a weekly scheduled workflow and `workflow_dispatch`, outside the required PR CI path. If it fails, first decide whether the link should be fixed in the canonical content data or whether the remote service is intentionally excluded from automated probing. Only update the allowlist for the second case, and keep the reason specific enough for later cleanup. Broad domain allowlist entries should be rare; prefer exact or prefix entries for known archived links.

## PR Agent Context
- `CI` uploads raw `.coverage*` data, combines it into `coverage.xml`, and publishes both artifact outputs for downstream PR context analysis.
- `pr-agent-context` runs as part of `CI` on pull requests and uses `coverage-xml` to compute patch coverage commentary.
- `pr-agent-context-refresh` reruns on review and later check signals with `publish_mode: append`, reusing the latest `coverage-xml` artifact from the matching `CI` run when possible.
- Both reusable-workflow references must stay on the floating `v4` channel:
  - `uses: shaypal5/pr-agent-context/.github/workflows/pr-agent-context.yml@v4`
  - `tool_ref: v4`
- Do not repin `pr-agent-context` to a patch release in only one workflow. If a version override is ever needed, treat it as an explicit repo-wide compatibility change across both workflows.
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
4. If the discovered output needs no manual curation, run `courses backfill --publish-pr` to publish that freshly generated output.
5. If curation is needed, edit `data/teaching/` directly instead:
   - Curate public-facing material labels with `public_title` while preserving source titles in `title`.
   - Add `manual_overrides.materials_note` only when the public materials list needs reviewed explanatory context.
   - Run `courses render`, `courses validate`, and `courses plan`.
   - Open a normal reviewed PR for the curated YAML and generated markdown changes.

## Common Failure Cases
- Exit code `2`: OAuth variables are missing or token refresh failed.
- Exit code `3`: Drive listing failed or returned an unexpected error.
- Exit code `1`: data is incomplete, generated files are stale, or a URL is invalid.
- Exit code `4`: git push or `gh pr create` failed.

## Repairing Partial Runs
- Re-run `courses render` after editing YAML or automation rendering logic.
- Re-run `courses validate` before committing.
- If a sync partially succeeded, inspect `data/teaching/` and rerun `courses backfill --slug <slug>` for the affected course.
