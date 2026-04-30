from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from automation.config import Paths
from automation.data_io import load_courses, load_materials, save_courses, save_materials
from automation.models import Course, Material
from automation.rendering import file_diff_summary, inject_managed_block, render_course_page, render_teaching_block


@dataclass
class RenderResult:
    changed_files: list[str]


def _stale_generated_pages(paths: Paths, active_slugs: set[str]) -> list[Path]:
    stale_paths: list[Path] = []
    for page_path in paths.teaching_root.glob("*.md"):
        if page_path.stem in active_slugs:
            continue
        content = page_path.read_text(encoding="utf-8")
        if "<!-- GENERATED: edit data/teaching or automation sources instead of this file. -->" in content:
            stale_paths.append(page_path)
    return stale_paths


def current_state(paths: Paths) -> tuple[list[Course], dict[str, list[Material]]]:
    courses = load_courses(paths)
    materials = {course.slug: load_materials(paths, course.slug) for course in courses}
    return courses, materials


def write_data(paths: Paths, courses: list[Course], materials_by_slug: dict[str, list[Material]]) -> None:
    save_courses(paths, courses)
    for slug, materials in materials_by_slug.items():
        save_materials(paths, slug, materials)


def render_repository(
    paths: Paths,
    courses: list[Course],
    materials_by_slug: dict[str, list[Material]],
    dry_run: bool = False,
) -> RenderResult:
    changes: list[str] = []
    active_slugs = {course.slug for course in courses}
    for course in courses:
        rendered = render_course_page(course, materials_by_slug.get(course.slug, []), courses=courses)
        target = paths.teaching_root / f"{course.slug}.md"
        summary = file_diff_summary(target, rendered)
        if summary:
            changes.append(summary)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")

    for stale_path in _stale_generated_pages(paths, active_slugs):
        changes.append(f"D {stale_path.as_posix()}")
        if not dry_run:
            stale_path.unlink()

    teaching_existing = paths.teaching_index.read_text(encoding="utf-8")
    teaching_rendered = inject_managed_block(teaching_existing, render_teaching_block(courses))
    summary = file_diff_summary(paths.teaching_index, teaching_rendered)
    if summary:
        changes.append(summary)
    if not dry_run:
        paths.teaching_index.write_text(teaching_rendered, encoding="utf-8")
    return RenderResult(changed_files=changes)


def write_preview_repository(
    paths: Paths,
    courses: list[Course],
    materials_by_slug: dict[str, list[Material]],
) -> list[str]:
    preview_changes: list[str] = []
    if paths.preview_root.exists():
        shutil.rmtree(paths.preview_root)
    paths.preview_teaching_root.mkdir(parents=True, exist_ok=True)
    for course in courses:
        rendered = render_course_page(course, materials_by_slug.get(course.slug, []), courses=courses)
        target = paths.preview_teaching_root / f"{course.slug}.md"
        target.write_text(rendered, encoding="utf-8")
        preview_changes.append(target.as_posix())
    teaching_rendered = inject_managed_block(paths.teaching_index.read_text(encoding="utf-8"), render_teaching_block(courses))
    paths.preview_teaching_index.write_text(teaching_rendered, encoding="utf-8")
    preview_changes.append(paths.preview_teaching_index.as_posix())
    return preview_changes


def clean_preview_repository(paths: Paths) -> bool:
    if not paths.preview_root.exists():
        return False
    shutil.rmtree(paths.preview_root)
    return True
