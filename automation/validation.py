from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlparse

from automation.config import GENERATED_HEADER, PUBLIC_PAGE_GENERATED_HEADER, Paths
from automation.data_io import load_courses, load_materials, load_public_page_data
from automation.models import REQUIRED_COURSE_FIELDS, REQUIRED_MATERIAL_FIELDS, Course, Material
from automation.rendering import (
    inject_managed_block,
    PUBLIC_PAGE_TARGETS,
    render_course_page,
    render_public_page,
    render_teaching_block,
    should_render_course_page,
    visible_courses,
)


SUPPORTED_HOSTS = {
    "docs.google.com",
    "drive.google.com",
    "github.com",
    "databricks-prod-cloudfront.cloud.databricks.com",
}
ALLOW_EMPTY_REQUIRED_FIELDS = {"notes"}
ALLOW_NULL_REQUIRED_FIELDS = {"week"}


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _missing_fields(payload: dict, required_fields: list[str]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        if field not in payload:
            missing.append(field)
            continue
        value = payload[field]
        if value is None and field not in ALLOW_NULL_REQUIRED_FIELDS:
            missing.append(field)
            continue
        if isinstance(value, str) and field not in ALLOW_EMPTY_REQUIRED_FIELDS and not value.strip():
            missing.append(field)
    return missing


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def _supported_google_pattern(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc not in SUPPORTED_HOSTS:
        return True
    if parsed.netloc == "docs.google.com":
        return any(part in parsed.path for part in ("/document/", "/presentation/", "/spreadsheets/", "/forms/"))
    if parsed.netloc == "drive.google.com":
        return "/file/" in parsed.path or "/drive/folders/" in parsed.path
    return True


def validate_courses(courses: list[Course]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for course in courses:
        payload = course.to_dict()
        missing = _missing_fields(payload, REQUIRED_COURSE_FIELDS)
        if missing:
            errors.append(f"{course.slug}: missing course fields: {', '.join(missing)}")
        if not course.slug.strip():
            errors.append("Course slug must be non-empty.")
        elif not SLUG_PATTERN.fullmatch(course.slug):
            errors.append(f"{course.slug}: invalid slug format.")
        if course.slug in seen:
            errors.append(f"Duplicate course slug: {course.slug}")
        seen.add(course.slug)
        if course.visibility != "public":
            errors.append(f"{course.slug}: only public courses are supported in the published registry.")
        if course.syllabus_url and not _valid_url(course.syllabus_url):
            errors.append(f"{course.slug}: invalid syllabus_url {course.syllabus_url}")
    return errors


def validate_materials(slug: str, materials: list[Material]) -> list[str]:
    errors: list[str] = []
    for material in materials:
        payload = material.to_dict()
        missing = _missing_fields(payload, REQUIRED_MATERIAL_FIELDS)
        if missing:
            errors.append(f"{slug}: {material.title}: missing material fields: {', '.join(missing)}")
        if material.published and not _valid_url(material.url):
            errors.append(f"{slug}: {material.title}: invalid URL {material.url}")
        if material.url and not _supported_google_pattern(material.url):
            errors.append(f"{slug}: {material.title}: unsupported Google URL pattern {material.url}")
    return errors


def validate_generated_files(paths: Paths, courses: list[Course], materials_by_slug: dict[str, list[Material]]) -> list[str]:
    errors: list[str] = []
    for course in courses:
        target = paths.teaching_root / f"{course.slug}.md"
        if not should_render_course_page(course, materials_by_slug.get(course.slug, [])):
            if target.exists():
                content = target.read_text(encoding="utf-8")
                if GENERATED_HEADER in content:
                    errors.append(f"{target}: suppressed course page should not be generated.")
            continue
        if not target.exists():
            errors.append(f"Missing generated page for {course.slug}: {target}")
            continue
        content = target.read_text(encoding="utf-8")
        if GENERATED_HEADER not in content:
            errors.append(f"{target}: missing generated file header.")
        expected = render_course_page(
            course,
            materials_by_slug.get(course.slug, []),
            courses=courses,
            materials_by_slug=materials_by_slug,
        )
        if content != expected:
            errors.append(f"{target}: stale generated content. Run courses render.")
    teaching_current = paths.teaching_index.read_text(encoding="utf-8")
    try:
        teaching_expected = inject_managed_block(teaching_current, render_teaching_block(courses, materials_by_slug))
    except ValueError as exc:
        errors.append(f"{paths.teaching_index}: invalid managed block markers: {exc}")
    else:
        if teaching_current != teaching_expected:
            errors.append(f"{paths.teaching_index}: stale generated course listing. Run courses render.")
    return errors


def validate_internal_links(paths: Paths, courses: list[Course]) -> list[str]:
    errors: list[str] = []
    teaching_content = paths.teaching_index.read_text(encoding="utf-8")
    materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
    linked_courses = visible_courses(courses, materials_by_slug)
    for course in linked_courses:
        expected = f"/teaching/{course.slug}"
        if expected not in teaching_content:
            errors.append(f"{paths.teaching_index}: missing internal link to {expected}")
    for course in courses:
        expected = f"/teaching/{course.slug}"
        if expected in teaching_content and not (paths.teaching_root / f"{course.slug}.md").exists():
            errors.append(f"Internal link target missing for {expected}")
    return errors


def validate_public_page_data(page: str, page_data: dict) -> list[str]:
    errors: list[str] = []
    front_matter = page_data.get("front_matter", {})
    if not isinstance(front_matter, dict):
        errors.append(f"data/{page}.yml: front_matter must be a mapping.")
    selected = page_data.get("selected", {}) or {}
    selected_items = selected.get("items", []) if isinstance(selected, dict) else []
    anchors: set[str] = set()
    containers = []
    if page == "talks":
        containers = page_data.get("talks", []) or []
    elif page == "writing":
        containers = page_data.get("writing", []) or []
    elif page == "projects":
        for group in page_data.get("groups", []) or []:
            containers.extend(group.get("projects", []) or [])
    for item in containers:
        anchor = str(item.get("anchor", "") or "").strip()
        if anchor:
            if not SLUG_PATTERN.fullmatch(anchor):
                errors.append(f"data/{page}.yml: invalid anchor format: {anchor}")
            anchors.add(anchor)
        if not str(item.get("markdown", "") or "").strip():
            errors.append(f"data/{page}.yml: entry with anchor {anchor or '<none>'} is missing markdown.")
    for item in selected_items or []:
        anchor = str(item.get("anchor", "") or "").strip()
        title = str(item.get("title", "") or "").strip()
        if not anchor:
            errors.append(f"data/{page}.yml: selected item {title or '<untitled>'} is missing an anchor.")
        elif anchor not in anchors:
            errors.append(f"data/{page}.yml: selected item {title or anchor} points to missing anchor {anchor}.")
    return errors


def validate_public_pages(paths: Paths) -> list[str]:
    errors: list[str] = []
    for page, target_name in PUBLIC_PAGE_TARGETS.items():
        page_data = load_public_page_data(paths, page)
        errors.extend(validate_public_page_data(page, page_data))
        target = paths.repo_root / target_name
        if not target.exists():
            errors.append(f"Missing generated public page for {page}: {target}")
            continue
        content = target.read_text(encoding="utf-8")
        if PUBLIC_PAGE_GENERATED_HEADER not in content:
            errors.append(f"{target}: missing generated public page header.")
        expected = render_public_page(page, page_data)
        if content != expected:
            errors.append(f"{target}: stale generated public page. Run courses render.")
    return errors


def validate_repository(paths: Paths) -> list[str]:
    courses = load_courses(paths)
    materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
    errors = validate_courses(courses)
    for course in courses:
        errors.extend(validate_materials(course.slug, materials_by_slug.get(course.slug, [])))
    errors.extend(validate_generated_files(paths, courses, materials_by_slug))
    errors.extend(validate_internal_links(paths, courses))
    errors.extend(validate_public_pages(paths))
    return errors
