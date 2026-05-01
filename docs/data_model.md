# Data Model

## Course Schema
Required fields:
- `slug`
- `title`
- `subtitle`
- `institution`
- `role`
- `academic_period`
- `status`
- `source_drive_folder_id`
- `source_drive_folder_name`
- `summary`
- `visibility`

Optional fields:
- `syllabus_url`
- `hero_note`
- `tags`
- `manual_overrides`
- `review_notes`
- `course_family`
- `section`
- `is_generalized`
- `redirect_from`

`redirect_from` stores old public paths for renamed generated course pages. Use
absolute site paths such as `/teaching/old-slug` or `/teaching/old-slug.html`.
Validation rejects duplicate aliases and aliases that collide with current
public URLs.

### Course Manual Overrides
`manual_overrides` contains reviewed presentation controls that should stay with
the canonical course record instead of being hand-edited into generated pages.
Common keys include:
- `opening_paragraph`
- `organizing_team`
- `lectures`
- `lectures_heading`
- `lectures_note`
- `syllabus_markdown`
- `syllabus_note`
- `materials_note`
- `hide_empty_materials`
- `publish_material_file_ids`
- `iteration_label`
- `iteration_sort_key`
- `section_label`
- `teaching_index_sort_key`

`materials_note` renders immediately below the course materials heading and
before the materials list. Use it for public curation context, for example when
a semester page intentionally exposes a compact subset of the reviewed source
materials.

`publish_material_file_ids` force-publishes reviewed Drive file IDs that the
classifier would otherwise exclude.

## Material Schema
Required fields:
- `title`
- `url`
- `kind`
- `week`
- `section`
- `source_file_id`
- `source_mime_type`
- `published`
- `sort_key`
- `notes`

Optional fields:
- `description`
- `public_title`

`title` is the source title preserved from the reviewed material record. It is
used for stable sorting, review, validation messages, and future sync context.

`public_title` is optional curated public link text. When present and non-empty,
the renderer uses it as the visible material link label while preserving `title`
internally. When absent, the renderer derives public link text from `title` by
stripping known noisy suffixes such as presenter or Google Slides markers.

## Ordering Rules
- Courses: active first, then academic period, then title.
- Materials: week, section, sort key, then title.

## Editable Vs. Inferred Fields
- Machine-inferred by default: `slug`, `title`, `institution`, `role`, `academic_period`, `kind`, `week`, `section`, `sort_key`.
- Manually editable after sync: `summary`, `subtitle`, `hero_note`, `syllabus_url`, `tags`, `manual_overrides`, `review_notes`, and material `notes`, `description`, and `public_title`.
- Source titles should remain intact in material `title`; curate public-facing link text with `public_title` instead of overwriting the source title.

## Slug Rules
- Slugs must be unique across all courses.
- Slugs are lowercase ASCII, with non-alphanumeric characters collapsed to `-`.
- Existing public URLs should be preserved when migrating legacy pages.

## Public Page Data
The Talks, Blog, and Code pages use lightweight YAML data files at:
- `data/talks.yml`
- `data/writing.yml`
- `data/projects.yml`

Each file owns the page front matter, selected-item list, stable in-page anchors,
and the markdown entries rendered into the public page. The generated pages are:
- `talks.md`
- `blog.md`
- `code.md`

If a generated public page is renamed, add `redirect_from` aliases to its
`front_matter` block in the data file so the old URL keeps working. See
`docs/redirects.md` for the redirect policy.

Selected sections are structured as `selected.heading` plus `selected.items`.
Each selected item must point to an anchor owned by a rendered talk, writing item,
or project entry. Code projects are additionally grouped under `groups[].title`
to preserve the current public sections.

Run `python3 -m automation.cli courses render` after editing these files. The
existing `courses validate` and `courses plan` commands also check these generated
pages for stale output.
