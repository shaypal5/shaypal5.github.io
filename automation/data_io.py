from __future__ import annotations

from pathlib import Path

import yaml

from automation.config import Paths
from automation.models import Course, Material


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return loaded


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False)


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
