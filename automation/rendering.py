from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path
import re
from typing import Any

from automation.config import GENERATED_HEADER, TEACHING_MARKER_END, TEACHING_MARKER_START
from automation.models import Course, Material

PINNED_TEACHING_INDEX_ORDER = {
    "deep-learning": "01",
    "text-mining": "02",
    "econml": "03",
    "datanights": "04",
    "data-vis": "05",
    "bigdata22": "06",
}

GENERIC_SUMMARY_PREFIX = "Teaching materials extracted from Google Drive folder"
UNKNOWN_METADATA_VALUES = {"", "unknown institution", "tbd"}

MATERIAL_TITLE_SUFFIX_PATTERNS = (
    re.compile(r"\s+[-\u2013\u2014]\s+[^-\u2013\u2014]*@\s*[A-Z][A-Za-z. ]+\s*$"),
    re.compile(r"\s+[-\u2013\u2014]\s+Shay Palachy(?: Affek)?\s*$", re.IGNORECASE),
    re.compile(r"\s+[-\u2013\u2014]\s+Google Slides\s*$", re.IGNORECASE),
)


def sort_courses(courses: list[Course]) -> list[Course]:
    def key(course: Course) -> tuple[int, str, str]:
        current_rank = 0 if course.status == "active" else 1
        return (current_rank, course.academic_period.lower(), course.title.lower())

    return sorted(courses, key=key)


def _academic_period_sort_value(course: Course) -> tuple[int, int, str]:
    digits = "".join(char for char in course.academic_period if char.isdigit())
    if not digits:
        return (1, 0, course.academic_period.casefold())
    return (0, -int(digits[:4]), course.academic_period.casefold())


def _teaching_index_sort_key(course: Course) -> tuple[int, str, int, int, int, str]:
    manual_key = course.manual_overrides.get("teaching_index_sort_key")
    pinned_key = PINNED_TEACHING_INDEX_ORDER.get(course.course_family or course.slug)
    explicit_key = manual_key if manual_key is not None else pinned_key
    if explicit_key is not None:
        return (0, str(explicit_key), 0, 0, 0, course.title.casefold())
    current_rank = 0 if course.status == "active" else 1
    period_missing, period_value, period_label = _academic_period_sort_value(course)
    return (1, "", current_rank, period_missing, period_value, f"{period_label}::{course.title.casefold()}")


def _public_materials(materials: list[Material]) -> list[Material]:
    return [
        item
        for item in sort_materials(materials)
        if item.published and item.kind not in {"outline", "syllabus"}
    ]


def _published_lecture_materials(materials: list[Material]) -> list[Material]:
    return [item for item in _public_materials(materials) if item.kind in {"slides", "notebook"}]


def should_render_course_page(course: Course, materials: list[Material]) -> bool:
    if course.is_generalized:
        return True
    if course.manual_overrides.get("lectures") or course.manual_overrides.get("organizing_team"):
        return True
    if course.summary.strip().startswith(GENERIC_SUMMARY_PREFIX):
        return False
    return bool(_published_lecture_materials(materials))


def visible_courses(courses: list[Course], materials_by_slug: dict[str, list[Material]] | None = None) -> list[Course]:
    generalized_families = {course.course_family for course in courses if course.is_generalized and course.course_family}
    visible = [
        course
        for course in sort_courses(courses)
        if (materials_by_slug is None or should_render_course_page(course, materials_by_slug.get(course.slug, [])))
        and (not course.course_family or course.is_generalized or course.course_family not in generalized_families)
    ]
    return sorted(visible, key=_teaching_index_sort_key)


def sort_materials(materials: list[Material]) -> list[Material]:
    return sorted(
        materials,
        key=lambda item: (
            item.week is None,
            item.week or 0,
            item.section.lower(),
            item.sort_key.lower(),
            item.title.lower(),
        ),
    )


def public_material_title(material: Material) -> str:
    explicit = str(material.public_title or "").strip()
    if explicit:
        return explicit
    source_title = str(material.title or "").strip()
    title = source_title
    previous = ""
    while title and title != previous:
        previous = title
        for pattern in MATERIAL_TITLE_SUFFIX_PATTERNS:
            title = pattern.sub("", title).strip()
    return title or source_title


def _iteration_label(course: Course) -> str:
    manual_label = str(course.manual_overrides.get("iteration_label", "") or "").strip()
    if manual_label:
        return manual_label
    label = course.academic_period or "TBD"
    if course.section:
        section_label = str(course.manual_overrides.get("section_label", "Semester") or "Semester").strip()
        label += f" {section_label} {course.section}"
    return label


def _iteration_sort_key(course: Course) -> tuple[int, str]:
    manual_key = course.manual_overrides.get("iteration_sort_key")
    if manual_key is not None:
        return (0, str(manual_key))
    return (1, f"{course.academic_period.lower()}::{course.title.lower()}::{course.section.lower()}")


def _course_metadata_parts(course: Course) -> list[str]:
    parts = []
    institution = str(course.institution or "").strip()
    if institution.casefold() not in UNKNOWN_METADATA_VALUES:
        parts.append(institution)
    role = str(course.role or "").strip()
    if role.casefold() not in UNKNOWN_METADATA_VALUES:
        parts.append(role)
    academic_period = str(course.academic_period or "").strip()
    if academic_period.casefold() not in UNKNOWN_METADATA_VALUES:
        parts.append(academic_period)
    return parts


def _render_course_metadata(course: Course) -> str:
    parts = _course_metadata_parts(course)
    if not parts:
        return ""
    separator = '<span class="course-meta-separator" aria-hidden="true">/</span>'
    return '<p class="course-meta">' + separator.join(f"<span>{escape(part)}</span>" for part in parts) + "</p>"


def _render_named_list_item(item: Any) -> str:
    if isinstance(item, dict):
        name = str(item.get("name", "") or "").strip()
        role = str(item.get("role", "") or "").strip()
        company = str(item.get("company", "") or "").strip()
        details = ", ".join(part for part in [role, company] if part)
        if name and details:
            return f"* **{name}** - {details}"
        if name:
            return f"* {name}"
        if details:
            return f"* {details}"
        return ""
    text = str(item or "").strip()
    return f"* {text}" if text else ""


def _render_lecture_item(item: Any) -> list[str]:
    if not isinstance(item, dict):
        text = str(item or "").strip()
        return [f"* {text}"] if text else []
    title = str(item.get("title", "") or "").strip()
    speaker = str(item.get("speaker", "") or "").strip()
    description = str(item.get("description", "") or "").strip()
    link = str(item.get("link", "") or "").strip()
    status = str(item.get("status", "") or "").strip()
    label = title or "Untitled session"
    if link:
        label = f"[{label}]({link}){{:target=\"_blank\"}}"
    if speaker:
        label = f"{label} - {speaker}"
    if status:
        label = f"{label} ({status})"
    lines = [f"* {label}"]
    if description:
        lines.append(f"  {description}")
    return lines


def render_course_page(
    course: Course,
    materials: list[Material],
    courses: list[Course] | None = None,
    materials_by_slug: dict[str, list[Material]] | None = None,
) -> str:
    lines = [
        "---",
        "layout: page",
        f"title: {course.title}",
        f"subtitle: {course.subtitle}",
        "---",
        "",
        GENERATED_HEADER,
        "",
        f"## {course.title}",
        "",
    ]
    metadata = _render_course_metadata(course)
    if metadata:
        lines.extend([metadata, ""])
    lines.extend([course.summary, ""])
    if course.is_generalized and courses:
        iterations = []
        for item in sort_courses(courses):
            if item.course_family != course.course_family or item.is_generalized:
                continue
            if materials_by_slug is not None and not should_render_course_page(item, materials_by_slug.get(item.slug, [])):
                continue
            iterations.append(item)
        iterations = sorted(iterations, key=_iteration_sort_key)
        lines.extend(["## Course Iterations", ""])
        if iterations:
            for item in iterations:
                lines.append(f"* [{_iteration_label(item)}](/teaching/{item.slug})")
            lines.append("")
        else:
            lines.extend(["TBA", ""])
    opening_paragraph = str(course.manual_overrides.get("opening_paragraph", "") or "").strip()
    if opening_paragraph:
        lines.extend([opening_paragraph, ""])
    if course.hero_note:
        lines.extend([course.hero_note, ""])
    organizing_team = course.manual_overrides.get("organizing_team", []) or []
    if organizing_team:
        lines.extend(["## Organizing Team", ""])
        for item in organizing_team:
            rendered = _render_named_list_item(item)
            if rendered:
                lines.append(rendered)
        lines.append("")
    lectures = course.manual_overrides.get("lectures", []) or []
    lectures_heading = str(course.manual_overrides.get("lectures_heading", "## Lectures") or "## Lectures").strip()
    lectures_note = str(course.manual_overrides.get("lectures_note", "") or "").strip()
    if lectures or lectures_note:
        lines.extend([lectures_heading, ""])
        if lectures_note:
            lines.extend([lectures_note, ""])
        if lectures:
            for item in lectures:
                lines.extend(_render_lecture_item(item))
                lines.append("")
        else:
            lines.extend(["TBA", ""])
    syllabus_markdown = str(course.manual_overrides.get("syllabus_markdown", "") or "").strip()
    syllabus_note = str(course.manual_overrides.get("syllabus_note", "") or "").strip()
    if course.syllabus_url or syllabus_markdown or syllabus_note:
        lines.extend(["## Course Outline", ""])
        if course.syllabus_url:
            lines.extend([f"**[Course Syllabus]({course.syllabus_url}){{:target=\"_blank\"}}**", ""])
        if syllabus_markdown:
            lines.extend(syllabus_markdown.splitlines())
            lines.append("")
        elif syllabus_note:
            lines.extend([syllabus_note, ""])
    grouped: dict[tuple[int | None, str], list[Material]] = defaultdict(list)
    for material in _public_materials(materials):
        grouped[(material.week, material.section or "Course Materials")].append(material)
    hide_empty_materials = bool(course.manual_overrides.get("hide_empty_materials", False))
    if not grouped and hide_empty_materials:
        return "\n".join(lines).rstrip() + "\n"
    material_heading = "## Shared Course Materials" if course.is_generalized else "## Course Materials"
    lines.extend([material_heading, ""])
    materials_note = str(course.manual_overrides.get("materials_note", "") or "").strip()
    if materials_note:
        lines.extend([materials_note, ""])
    if not grouped:
        lines.append("TBA")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"
    active_week = None
    for (week, section), section_items in grouped.items():
        if week != active_week:
            active_week = week
            if week is None:
                lines.extend(["### General Materials", ""])
            else:
                lines.extend([f"### Week {week}", ""])
        if section and section not in {"Course Materials", "Weekly Materials"}:
            lines.extend([f"#### {section}", ""])
        for item in section_items:
            trailing = ""
            if item.description:
                trailing = f" - {item.description}"
            elif item.notes:
                trailing = f" ({item.notes})"
            lines.append(f"* **[{public_material_title(item)}]({item.url}){{:target=\"_blank\"}}**{trailing}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_teaching_block(courses: list[Course], materials_by_slug: dict[str, list[Material]] | None = None) -> str:
    ordered = visible_courses(courses, materials_by_slug)
    current_courses = [course for course in ordered if course.status == "active"]
    archived_courses = [course for course in ordered if course.status != "active"]

    rendered = [TEACHING_MARKER_START, ""]
    if current_courses:
        rendered.extend(["#### Current Courses", "", '<ul class="teaching-course-list">'])
        for course in current_courses:
            metadata = _render_course_metadata(course)
            rendered.append(f'  <li><a href="/teaching/{course.slug}">{escape(course.title)}</a>{metadata}</li>')
        rendered.extend(["</ul>", ""])
    if archived_courses:
        rendered.extend(["#### Archived Teaching", "", '<ul class="teaching-course-list">'])
        for course in archived_courses:
            metadata = _render_course_metadata(course)
            rendered.append(f'  <li><a href="/teaching/{course.slug}">{escape(course.title)}</a>{metadata}</li>')
        rendered.extend(["</ul>", ""])

    rendered.extend(['<div class="teaching-course-summaries" markdown="1">', ""])
    for index, course in enumerate(ordered):
        metadata = _render_course_metadata(course)
        rendered.extend([f'<section class="teaching-course-summary" id="{escape(course.slug)}" markdown="1">', f"## {course.title}", ""])
        if metadata:
            rendered.extend([metadata, ""])
        rendered.extend([course.summary, "", f"[View course materials](/teaching/{course.slug})", "</section>", ""])
    rendered.append("</div>")
    rendered.append(TEACHING_MARKER_END)
    return "\n".join(rendered).rstrip() + "\n"


def inject_managed_block(existing: str, generated_block: str) -> str:
    if TEACHING_MARKER_START not in existing or TEACHING_MARKER_END not in existing:
        raise ValueError("teaching.md is missing managed markers.")
    before, remainder = existing.split(TEACHING_MARKER_START, 1)
    _, after = remainder.split(TEACHING_MARKER_END, 1)
    return before.rstrip() + "\n\n" + generated_block.rstrip() + "\n" + after.lstrip("\n")


def file_diff_summary(path: Path, new_content: str) -> str | None:
    if not path.exists():
        return f"A {path.as_posix()}"
    old_content = path.read_text(encoding="utf-8")
    if old_content == new_content:
        return None
    return f"M {path.as_posix()}"
