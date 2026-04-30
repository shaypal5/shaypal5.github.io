# Agent Instructions

## Scope
- This repository is a Jekyll personal site with local Python automation for teaching-content workflows.
- Treat `data/teaching/` as the canonical source for teaching content.
- Treat `teaching/*.md` and the managed block in `teaching.md` as generated artifacts.
- Treat `data/talks.yml`, `data/writing.yml`, and `data/projects.yml` as the canonical source for Talks, Blog, and Code page content.
- Treat `talks.md`, `blog.md`, and `code.md` as generated artifacts.

## Required Commands
- Install Python dependencies: `pip install .`
- Run tests: `python3 -m unittest discover -s tests`
- Render teaching pages: `python3 -m automation.cli courses render`
- Validate teaching content: `python3 -m automation.cli courses validate`
- Preview rendered diffs: `python3 -m automation.cli courses plan`
- Backfill from Google Drive: `python3 -m automation.cli courses backfill --dry-run`
- Build the site: `bundle exec jekyll build`

## Editing Rules
- Do not hand-edit generated teaching pages unless you are also updating the renderer or canonical data.
- Prefer editing:
  - `data/teaching/courses.yml`
  - `data/teaching/materials/*.yml`
  - `data/talks.yml`
  - `data/writing.yml`
  - `data/projects.yml`
  - `automation/*`
  - `docs/*` for internal process documentation
- Keep Google Drive integration read-only.
- Preserve stable public slugs for existing course pages.
- Keep internal automation and planning files excluded from site deployment.

## CI And PR Rules
- The main CI producer workflow is `.github/workflows/teaching-validation.yml` and is named `CI`.
- PR agent context is driven by:
  - `.github/workflows/teaching-validation.yml`
  - `.github/workflows/pr-agent-context-refresh.yml`
  - `.github/pr-agent-context-template.md`
- Keep `pr-agent-context` refresh flow in append mode unless there is a specific reason to change it.
- Coverage artifacts expected by `pr-agent-context`:
  - raw coverage prefix: `pr-agent-context-coverage-*`
  - combined report artifact: `coverage-xml`

## Branch And Commit Rules
- Default feature branch prefix: `codex/`
- Do not rewrite or reset user changes.
- Keep related changes in coherent commits.
- For work that extends an already-open PR, continue on the existing PR branch unless explicitly told to split it.

## Architecture Boundaries
- `automation/` contains local orchestration, rendering, validation, and publish helpers.
- `docs/` contains human-oriented long-form planning and architecture docs.
- `.agent-plan.md` is the short-lived execution tracker for agents; do not move detailed plans into it.
- `llms.txt` is a repo index for agents; keep it dense and structural.
