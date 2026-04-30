# Review Workflow

## Review-First Policy
Drive discovery is allowed to infer courses and materials automatically, but the repo data files are the reviewed source of truth. Automation may draft data, yet publication happens only through git review and a pull request.

## Expected Agent Behavior
- Prefer public, stable links when classifying materials.
- Skip private or non-shareable assets instead of publishing broken links.
- Record ambiguous items in `review_notes` or material `notes`.
- Preserve existing slugs and refined summaries when a Drive folder is rediscovered later.
- Preserve source material titles in `title`; use `public_title` when public link text needs a shorter or cleaner label.

## Manual Overrides
- Course-level overrides belong in `manual_overrides` or the editable top-level course fields.
- Use `manual_overrides.materials_note` for reviewed public context that should render above a course materials list.
- Material-level manual edits belong directly in the material record.
- Generated markdown files should not be edited directly; they are overwritten by `courses render`.

## PR Expectations
- Include a concise summary of affected courses and any flagged ambiguities.
- Use the `teaching` label.
- Keep the PR non-draft only after validation has passed locally.
