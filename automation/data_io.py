from __future__ import annotations

from pathlib import Path

import yaml

from automation.config import Paths
from automation.models import Course, ExcludedMaterial, Material


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return loaded


def dump_yaml_text(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml_text(payload), encoding="utf-8")


def iter_teaching_yaml_paths(paths: Paths) -> list[Path]:
    return [paths.data_root / "courses.yml", *sorted(paths.materials_root.glob("*.yml"))]


def format_teaching_yaml(paths: Paths, *, check: bool = False) -> list[Path]:
    changed: list[Path] = []
    for path in iter_teaching_yaml_paths(paths):
        if not path.exists():
            continue
        rendered = dump_yaml_text(_read_yaml(path))
        current = path.read_text(encoding="utf-8")
        if current == rendered:
            continue
        changed.append(path)
        if not check:
            path.write_text(rendered, encoding="utf-8")
    return changed


def load_courses(paths: Paths) -> list[Course]:
    payload = _read_yaml(paths.data_root / "courses.yml")
    items = payload.get("courses", []) or []
    return [Course.from_dict(item) for item in items]


def save_courses(paths: Paths, courses: list[Course]) -> None:
    ordered = sorted(courses, key=lambda course: course.slug)
    payload = {"courses": [course.to_dict() for course in ordered]}
    _write_yaml(paths.data_root / "courses.yml", payload)


def load_materials(paths: Paths, slug: str) -> list[Material]:
    payload = _read_yaml(paths.materials_root / f"{slug}.yml")
    items = payload.get("materials", []) or []
    return [Material.from_dict(item) for item in items]


def load_public_page_data(paths: Paths, page: str) -> dict:
    return _read_yaml(paths.site_data_root / f"{page}.yml")


def save_materials(paths: Paths, slug: str, materials: list[Material]) -> None:
    ordered = sorted(
        materials,
        key=lambda item: (
            item.week is None,
            item.week or 0,
            item.section.lower(),
            item.sort_key.lower(),
            item.title.lower(),
        ),
    )
    payload = {"course": slug, "materials": [item.to_dict() for item in ordered]}
    _write_yaml(paths.materials_root / f"{slug}.yml", payload)


def save_excluded_materials(path: Path, items: list[ExcludedMaterial]) -> None:
    payload = {"excluded_materials": [item.to_dict() for item in items]}
    _write_yaml(path, payload)
