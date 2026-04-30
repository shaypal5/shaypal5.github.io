from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.cli import _attach_syllabus_content, _discover_materials
from automation.config import build_paths
from automation.google_drive import DriveClient
from automation.naming import infer_course_from_folder, is_valid_course_folder_name


def _family_rank(course) -> tuple[str, str]:
    return (course.academic_period, course.section)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "families",
        nargs="*",
        default=["data-vis", "deep-learning", "text-mining"],
        help="Course families to inspect.",
    )
    args = parser.parse_args()

    paths = build_paths()
    output_root = paths.preview_root / "latest-syllabi"
    output_root.mkdir(parents=True, exist_ok=True)

    client = DriveClient.from_env()
    folders = client.discover_course_folders(limit=None)

    selected: dict[str, object] = {}
    for folder in folders:
        if not is_valid_course_folder_name(folder["name"]):
            continue
        course = infer_course_from_folder(folder["id"], folder["name"])
        if course.is_generalized or course.course_family not in args.families:
            continue
        current = selected.get(course.course_family)
        if current is None or _family_rank(course) > _family_rank(current):
            selected[course.course_family] = course

    for family in args.families:
        course = selected.get(family)
        if course is None:
            print(f"[latest-syllabi] No course iteration found for {family}.")
            continue
        materials = _discover_materials(client, course)
        course = _attach_syllabus_content(client, course, materials)
        syllabus_markdown = str(course.manual_overrides.get("syllabus_markdown", "") or "").strip()
        output_path = output_root / f"{family}-{course.slug}.md"
        output_path.write_text(
            "\n".join(
                [
                    f"# {course.title}",
                    "",
                    f"* Family: `{family}`",
                    f"* Iteration: `{course.slug}`",
                    f"* Source folder: `{course.source_drive_folder_name}`",
                    f"* Syllabus URL: {course.syllabus_url or 'N/A'}",
                    "",
                    syllabus_markdown or "_No inline syllabus markdown extracted._",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(f"[latest-syllabi] Wrote {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
