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

## Ordering Rules
- Courses: active first, then academic period, then title.
- Materials: week, section, sort key, then title.

## Editable Vs. Inferred Fields
- Machine-inferred by default: `slug`, `title`, `institution`, `role`, `academic_period`, `kind`, `week`, `section`, `sort_key`.
- Manually editable after sync: `summary`, `subtitle`, `hero_note`, `syllabus_url`, `tags`, `manual_overrides`, `review_notes`, and any material `notes`.

## Slug Rules
- Slugs must be unique across all courses.
- Slugs are lowercase ASCII, with non-alphanumeric characters collapsed to `-`.
- Existing public URLs should be preserved when migrating legacy pages.
