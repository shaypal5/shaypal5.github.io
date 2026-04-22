from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from automation.config import GENERATED_HEADER, TEACHING_MARKER_END, TEACHING_MARKER_START
from automation.models import Course, Material


def sort_courses(courses: list[Course]) -> list[Course]:
    def key(course: Course) -> tuple[int, str, str]:
        current_rank = 0 if course.status == "active" else 1
        return (current_rank, course.academic_period.lower(), course.title.lower())

    return sorted(courses, key=key)


def visible_courses(courses: list[Course]) -> list[Course]:
    generalized_families = {course.course_family for course in courses if course.is_generalized and course.course_family}
    return [
        course
        for course in sort_courses(courses)
        if not course.course_family or course.is_generalized or course.course_family not in generalized_families
    ]


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


def _iteration_label(course: Course) -> str:
    label = course.academic_period or "TBD"
    if course.section:
        label += f" Section {course.section}"
    return label


def render_course_page(course: Course, materials: list[Material], courses: list[Course] | None = None) -> str:
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
        course.summary,
        "",
    ]
    if course.is_generalized and courses:
        iterations = [
            item
            for item in sort_courses(courses)
            if item.course_family == course.course_family and not item.is_generalized
        ]
        lines.extend(["## Course Iterations", ""])
        if iterations:
            for item in iterations:
                lines.append(f"* [{_iteration_label(item)}](/teaching/{item.slug})")
            lines.append("")
        else:
            lines.extend(["TBA", ""])
    if course.hero_note:
        lines.extend([course.hero_note, ""])
    if course.syllabus_url:
        lines.extend(
            [
                "## Course Outline",
                "",
                f"**[Course Syllabus]({course.syllabus_url}){{:target=\"_blank\"}}**",
                "",
            ]
        )
    grouped: dict[tuple[int | None, str], list[Material]] = defaultdict(list)
    for material in sort_materials(materials):
        if not material.published:
            continue
        grouped[(material.week, material.section or "Course Materials")].append(material)
    material_heading = "## Shared Course Materials" if course.is_generalized else "## Course Materials"
    lines.extend([material_heading, ""])
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
            lines.append(f"**[{item.title}]({item.url}){{:target=\"_blank\"}}**{trailing}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_teaching_block(courses: list[Course]) -> str:
    rendered = [TEACHING_MARKER_START, "", "#### Courses", ""]
    ordered = visible_courses(courses)
    for course in ordered:
        rendered.append(f"* [{course.title}](/teaching/{course.slug})")
    rendered.extend(["", "|", ""])
    for index, course in enumerate(ordered):
        rendered.extend([f"## {course.title}", "", course.summary, "", f"[Course page is here](/teaching/{course.slug})"])
        if index != len(ordered) - 1:
            rendered.extend(["", "|", ""])
        else:
            rendered.append("")
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
