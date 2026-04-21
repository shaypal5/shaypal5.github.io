from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from typing import TYPE_CHECKING

from automation.config import (
    AuthConfigError,
    DiscoveryError,
    PublishError,
    ValidationError,
    build_paths,
)
from automation.data_io import load_courses, load_materials
from automation.naming import infer_course_from_folder, material_from_drive_item
from automation.publish import publish_changes
from automation.repository import render_repository, write_data
from automation.validation import validate_repository

if TYPE_CHECKING:
    from automation.google_drive import DriveClient
    from automation.models import Course, Material


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def cmd_render(_: argparse.Namespace) -> int:
    paths = build_paths()
    courses = load_courses(paths)
    materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
    result = render_repository(paths, courses, materials_by_slug, dry_run=False)
    _print_json({"action": "render", "changed_files": result.changed_files})
    return 0


def cmd_plan(_: argparse.Namespace) -> int:
    paths = build_paths()
    courses = load_courses(paths)
    materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
    result = render_repository(paths, courses, materials_by_slug, dry_run=True)
    _print_json({"action": "plan", "changed_files": result.changed_files})
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    paths = build_paths()
    errors = validate_repository(paths)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    _print_json({"action": "validate", "status": "ok"})
    return 0


def _merged_course(existing_by_id: dict[str, "Course"], folder: dict[str, str]) -> "Course":
    current = existing_by_id.get(folder["id"])
    inferred = infer_course_from_folder(folder["id"], folder["name"])
    if current is None:
        return inferred
    current = replace(
        current,
        source_drive_folder_id=folder["id"],
        source_drive_folder_name=folder["name"],
    )
    if not current.summary:
        current = replace(current, summary=inferred.summary)
    return current


def _discover_materials(client: "DriveClient", folder_id: str) -> list["Material"]:
    items = client.list_folder_items(folder_id)
    return [material_from_drive_item(item) for item in items if item.get("mimeType") != "application/vnd.google-apps.folder"]


def _backfill(args: argparse.Namespace, incremental: bool = False) -> int:
    from automation.google_drive import DriveClient

    paths = build_paths()
    client = DriveClient.from_env()
    discovered = client.discover_course_folders(limit=args.limit)
    existing_courses = load_courses(paths)
    existing_by_id = {course.source_drive_folder_id: course for course in existing_courses if course.source_drive_folder_id}
    selected = []
    for folder in discovered:
        course = _merged_course(existing_by_id, folder)
        if args.slug and course.slug != args.slug:
            continue
        selected.append(course)
    if incremental:
        selected_slugs = {course.slug for course in selected}
        courses = [course for course in existing_courses if course.slug not in selected_slugs] + selected
    else:
        selected_drive_folder_ids = {
            item.source_drive_folder_id for item in selected if item.source_drive_folder_id
        }
        preserved = [
            course
            for course in existing_courses
            if not course.source_drive_folder_id or course.source_drive_folder_id not in selected_drive_folder_ids
        ]
        courses = preserved + selected
    materials_by_slug = {course.slug: _discover_materials(client, course.source_drive_folder_id) for course in selected}
    for course in existing_courses:
        materials_by_slug.setdefault(course.slug, load_materials(paths, course.slug))
    if not args.dry_run:
        write_data(paths, courses, materials_by_slug)
        render_repository(paths, courses, materials_by_slug, dry_run=False)
        errors = validate_repository(paths)
        if errors:
            raise ValidationError("\n".join(errors))
        if args.publish_pr:
            publish = publish_changes(
                branch=args.branch,
                title=args.pr_title,
                body=args.pr_body,
                commit_message=args.commit_message,
            )
            _print_json(
                {
                    "action": "backfill",
                    "courses": [course.slug for course in selected],
                    "published_branch": publish.branch,
                    "pr_url": publish.pr_url,
                }
            )
            return 0
    result = render_repository(paths, courses, materials_by_slug, dry_run=True)
    _print_json({"action": "backfill", "courses": [course.slug for course in selected], "changed_files": result.changed_files})
    return 0


def cmd_backfill(args: argparse.Namespace) -> int:
    return _backfill(args, incremental=False)


def cmd_sync(args: argparse.Namespace) -> int:
    return _backfill(args, incremental=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m automation.cli")
    subparsers = parser.add_subparsers(dest="namespace", required=True)
    courses = subparsers.add_parser("courses")
    course_cmds = courses.add_subparsers(dest="command", required=True)

    shared_drive = argparse.ArgumentParser(add_help=False)
    shared_drive.add_argument("--dry-run", action="store_true")
    shared_drive.add_argument("--limit", type=int)
    shared_drive.add_argument("--slug")
    shared_drive.add_argument("--publish-pr", action="store_true")
    shared_drive.add_argument("--branch", default="codex/teaching-backfill")
    shared_drive.add_argument("--commit-message", default="Add teaching automation outputs")
    shared_drive.add_argument("--pr-title", default="Add teaching automation backfill")
    shared_drive.add_argument(
        "--pr-body",
        default=(
            "## Summary\n"
            "- add the teaching automation package and docs\n"
            "- migrate teaching content into structured YAML data and generated pages\n"
            "- add validation CI for teaching content\n"
        ),
    )

    backfill = course_cmds.add_parser("backfill", parents=[shared_drive])
    backfill.set_defaults(handler=cmd_backfill)

    sync = course_cmds.add_parser("sync", parents=[shared_drive])
    sync.set_defaults(handler=cmd_sync)

    render = course_cmds.add_parser("render")
    render.set_defaults(handler=cmd_render)

    validate = course_cmds.add_parser("validate")
    validate.set_defaults(handler=cmd_validate)

    plan = course_cmds.add_parser("plan")
    plan.set_defaults(handler=cmd_plan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except AuthConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except DiscoveryError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except PublishError as exc:
        print(str(exc), file=sys.stderr)
        return 4


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
