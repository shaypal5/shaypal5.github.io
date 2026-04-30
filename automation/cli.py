from __future__ import annotations

import argparse
import json
import subprocess
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
from automation.course_family_content import GENERALIZED_COURSE_CONTENT, apply_generalized_course_content
from automation.data_io import load_courses, load_materials
from automation.naming import (
    COURSE_SUFFIX,
    infer_course_from_folder,
    is_valid_course_folder_name,
    material_from_drive_item,
    should_descend_into_material_folder,
)
from automation.publish import publish_changes
from automation.repository import clean_preview_repository, render_repository, write_data, write_preview_repository
from automation.site_preview import build_preview_site, serve_preview_site
from automation.syllabus import (
    default_compact_syllabus_markdown,
    render_syllabus_markdown,
    select_syllabus_material,
    sorted_syllabus_materials,
)
from automation.validation import validate_repository

if TYPE_CHECKING:
    from automation.google_drive import DriveClient
    from automation.models import Course, Material


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _log(message: str) -> None:
    print(f"[teaching-automation] {message}")


def _preview(value: str, limit: int = 120) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


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


def cmd_clean_preview(_: argparse.Namespace) -> int:
    paths = build_paths()
    removed = clean_preview_repository(paths)
    _print_json({"action": "clean-preview", "removed": removed, "preview_root": paths.preview_root.as_posix()})
    return 0


def cmd_preview_site(args: argparse.Namespace) -> int:
    paths = build_paths()
    bundle_command = args.bundle_command
    try:
        if args.serve:
            _log(
                f"Serving preview site from {paths.preview_site_source_root} "
                f"at http://{args.host}:{args.port}."
            )
            source_root, build_root = serve_preview_site(
                paths,
                host=args.host,
                port=args.port,
                bundle_command=bundle_command,
            )
            _print_json(
                {
                    "action": "preview-site",
                    "mode": "serve",
                    "preview_source_root": source_root.as_posix(),
                    "preview_build_root": build_root.as_posix(),
                    "url": f"http://{args.host}:{args.port}",
                }
            )
            return 0
        _log(f"Building preview site from {paths.preview_site_source_root}.")
        source_root, build_root = build_preview_site(paths, bundle_command=bundle_command)
        _print_json(
            {
                "action": "preview-site",
                "mode": "build",
                "preview_source_root": source_root.as_posix(),
                "preview_build_root": build_root.as_posix(),
                "index_file": (build_root / "index.html").as_posix(),
            }
        )
        return 0
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(str(exc), file=sys.stderr)
        return 1


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
    return apply_generalized_course_content(current)


def _discover_materials(client: "DriveClient", course: "Course") -> list["Material"]:
    items = client.list_folder_items_recursive(
        course.source_drive_folder_id,
        should_descend=lambda item: should_descend_into_material_folder(item.get("name", ""), course.is_generalized),
    )
    return [
        material_from_drive_item(item, is_generalized_course=course.is_generalized)
        for item in items
        if item.get("mimeType") != "application/vnd.google-apps.folder"
    ]


def _attach_syllabus_content(client: "DriveClient", course: "Course", materials: list["Material"]) -> "Course":
    if course.is_generalized:
        return course
    syllabus_material = select_syllabus_material(materials)
    if syllabus_material is None:
        return course
    manual_overrides = dict(course.manual_overrides)
    if not course.syllabus_url:
        course = replace(course, syllabus_url=syllabus_material.url)
    if manual_overrides.get("syllabus_markdown"):
        return course
    for candidate in sorted_syllabus_materials(materials):
        if not candidate.source_file_id:
            continue
        try:
            exported_text = client.read_syllabus_source_text(
                candidate.source_file_id,
                candidate.source_mime_type,
            )
        except DiscoveryError as exc:
            _log(f"Skipping syllabus extraction for {course.slug}: {exc}")
            continue
        syllabus_markdown = render_syllabus_markdown(candidate, exported_text, course=course)
        if not syllabus_markdown:
            continue
        manual_overrides["syllabus_markdown"] = syllabus_markdown
        return replace(course, manual_overrides=manual_overrides)
    compact_fallback = default_compact_syllabus_markdown(course)
    if compact_fallback:
        manual_overrides["syllabus_markdown"] = compact_fallback
        return replace(course, manual_overrides=manual_overrides)
    return course


def _ensure_generalized_parents(courses: list["Course"]) -> list["Course"]:
    from automation.models import Course

    generalized_by_family = {
        course.course_family: course
        for course in courses
        if course.is_generalized and course.course_family
    }
    family_members: dict[str, list[Course]] = {}
    for course in courses:
        if course.is_generalized or not course.course_family:
            continue
        family_members.setdefault(course.course_family, []).append(course)
    synthesized: list[Course] = []
    for family, members in family_members.items():
        if family in generalized_by_family:
            continue
        if len(members) < 2 and family not in GENERALIZED_COURSE_CONTENT:
            continue
        exemplar = sorted(members, key=lambda item: (item.academic_period, item.slug))[0]
        synthesized.append(
            apply_generalized_course_content(
                Course(
                slug=family,
                title=exemplar.title,
                subtitle=f"{exemplar.title} across course iterations",
                institution=exemplar.institution,
                role=exemplar.role,
                academic_period="TBD",
                status="active" if any(item.status == "active" for item in members) else "archived",
                source_drive_folder_id=f"synthetic-generalized-{family}",
                source_drive_folder_name=f"{exemplar.title} - Generalized (synthetic)",
                summary=f"Teaching materials extracted from multiple Google Drive course folders for {exemplar.title}.",
                visibility="public",
                manual_overrides={"hide_empty_materials": True},
                review_notes="Synthetic generalized parent created automatically from multiple course iterations.",
                course_family=family,
                section="",
                is_generalized=True,
                )
            )
        )
    return courses + synthesized


def _backfill(args: argparse.Namespace, incremental: bool = False) -> int:
    from automation.google_drive import DriveClient

    paths = build_paths()
    _log("Refreshing Google OAuth access token.")
    client = DriveClient.from_env()
    _log(
        "Discovering Drive course folders"
        + (f" (limit={args.limit})" if args.limit is not None else "")
        + (f" filtered to slug={args.slug}" if args.slug else "")
        + "."
    )
    discovered = client.discover_course_folders(limit=args.limit)
    _log(f"Discovered {len(discovered)} candidate course folder(s).")
    for index, folder in enumerate(discovered, start=1):
        _log(
            f"Candidate {index}: name={folder['name']!r}, id={folder['id']}, "
            f"modified={folder.get('modifiedTime', 'unknown')}."
        )
    existing_courses = load_courses(paths)
    existing_by_id = {course.source_drive_folder_id: course for course in existing_courses if course.source_drive_folder_id}
    selected = []
    for folder in discovered:
        _log(f"Inspecting folder: {folder['name']} ({folder['id']})")
        if not is_valid_course_folder_name(folder["name"]):
            _log(
                f"Skipping folder {folder['name']} because it does not match the required "
                f"naming scheme: <non-empty title>{COURSE_SUFFIX!r}."
            )
            continue
        course = _merged_course(existing_by_id, folder)
        _log(
            f"Parsed folder into course slug={course.slug}, title={course.title!r}, "
            f"period={course.academic_period!r}."
        )
        if args.slug and course.slug != args.slug:
            _log(f"Skipping {folder['name']} because slug {course.slug} does not match requested slug {args.slug}.")
            continue
        selected.append(course)
    _log(f"Selected {len(selected)} course(s) for processing.")
    materials_by_slug = {}
    selected_with_syllabus = []
    for course in selected:
        _log(f"Listing materials for {course.slug} from folder {course.source_drive_folder_id}.")
        materials = _discover_materials(client, course)
        course = _attach_syllabus_content(client, course, materials)
        materials_by_slug[course.slug] = materials
        selected_with_syllabus.append(course)
        _log(f"Found {len(materials)} material item(s) for {course.slug}.")
        for index, material in enumerate(materials, start=1):
            _log(
                f"Material {index} for {course.slug}: title={material.title!r}, kind={material.kind}, "
                f"week={material.week}, section={material.section!r}, published={material.published}, "
                f"url={_preview(material.url)}."
            )
        if course.manual_overrides.get("syllabus_markdown"):
            _log(f"Extracted inline syllabus markdown for {course.slug}.")
    selected = selected_with_syllabus
    if incremental:
        selected_slugs = {course.slug for course in selected}
        courses = [course for course in existing_courses if course.slug not in selected_slugs] + selected
    else:
        selected_slugs = {item.slug for item in selected}
        selected_drive_folder_ids = {
            item.source_drive_folder_id for item in selected if item.source_drive_folder_id
        }
        preserved = [
            course
            for course in existing_courses
            if course.slug not in selected_slugs
            and (not course.source_drive_folder_id or course.source_drive_folder_id not in selected_drive_folder_ids)
        ]
        courses = preserved + selected
    courses = _ensure_generalized_parents(courses)
    for course in existing_courses:
        materials_by_slug.setdefault(course.slug, load_materials(paths, course.slug))
    if not args.dry_run:
        _log("Writing structured teaching data to the repository.")
        write_data(paths, courses, materials_by_slug)
        _log("Rendering teaching pages from structured data.")
        render_repository(paths, courses, materials_by_slug, dry_run=False)
        _log("Running repository validation.")
        errors = validate_repository(paths)
        if errors:
            raise ValidationError("\n".join(errors))
        if args.publish_pr:
            _log(f"Publishing changes through branch {args.branch}.")
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
    _log("Computing dry-run render diff.")
    result = render_repository(paths, courses, materials_by_slug, dry_run=True)
    preview_files = write_preview_repository(paths, courses, materials_by_slug)
    _log(f"Wrote {len(preview_files)} preview file(s) under {paths.preview_root}.")
    _print_json(
        {
            "action": "backfill",
            "courses": [course.slug for course in selected],
            "changed_files": result.changed_files,
            "preview_root": paths.preview_root.as_posix(),
            "preview_files": preview_files,
        }
    )
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

    clean_preview = course_cmds.add_parser("clean-preview")
    clean_preview.set_defaults(handler=cmd_clean_preview)

    preview_site = course_cmds.add_parser("preview-site")
    preview_site.add_argument("--serve", action="store_true")
    preview_site.add_argument("--host", default="127.0.0.1")
    preview_site.add_argument("--port", type=int, default=4001)
    preview_site.add_argument("--bundle-command", default="bundle")
    preview_site.set_defaults(handler=cmd_preview_site)

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
