import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from automation import cli
from automation.config import AuthConfigError, DiscoveryError, PublishError, ValidationError, build_paths
from automation.models import Course, Material
from automation.repository import RenderResult


def sample_course(slug: str = "course-one", folder_id: str = "folder-1", summary: str = "summary") -> Course:
    return Course(
        slug=slug,
        title="Course One",
        subtitle="Subtitle",
        institution="Inst",
        role="Instructor",
        academic_period="2025",
        status="active",
        source_drive_folder_id=folder_id,
        source_drive_folder_name=f"{slug} CF",
        summary=summary,
        visibility="public",
    )


def sample_material(title: str = "Slides", url: str = "https://example.com") -> Material:
    return Material(
        title=title,
        url=url,
        kind="slides",
        week=1,
        section="Course Materials",
        source_file_id="file-1",
        source_mime_type="application/pdf",
        published=True,
        sort_key="01-slides",
        notes="",
    )


class CliTests(unittest.TestCase):
    def test_print_json_outputs_payload(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cli._print_json({"b": 2, "a": 1})
        self.assertIn('"a": 1', buffer.getvalue())

    def test_cmd_render_plan_and_validate(self) -> None:
        with mock.patch.object(cli, "build_paths", return_value=object()), \
            mock.patch.object(cli, "load_courses", return_value=[sample_course()]), \
            mock.patch.object(cli, "load_materials", return_value=[sample_material()]), \
            mock.patch.object(cli, "render_repository", return_value=RenderResult(changed_files=["M teaching.md"])) as render, \
            mock.patch.object(cli, "validate_repository", return_value=[]), \
            mock.patch.object(cli, "_print_json") as print_json:
            self.assertEqual(cli.cmd_render(argparse.Namespace()), 0)
            render.assert_called_with(mock.ANY, mock.ANY, mock.ANY, dry_run=False)
            self.assertEqual(cli.cmd_plan(argparse.Namespace()), 0)
            render.assert_called_with(mock.ANY, mock.ANY, mock.ANY, dry_run=True)
            self.assertEqual(cli.cmd_validate(argparse.Namespace()), 0)
            print_json.assert_called()

    def test_cmd_validate_prints_errors(self) -> None:
        buffer = io.StringIO()
        with mock.patch.object(cli, "build_paths", return_value=object()), \
            mock.patch.object(cli, "validate_repository", return_value=["bad data"]), \
            contextlib.redirect_stderr(buffer):
            self.assertEqual(cli.cmd_validate(argparse.Namespace()), 1)
        self.assertIn("bad data", buffer.getvalue())

    def test_merged_course_and_discover_materials(self) -> None:
        course = sample_course(summary="")
        merged = cli._merged_course({"folder-1": course}, {"id": "folder-1", "name": "Folder CF"})
        self.assertEqual(merged.source_drive_folder_name, "Folder CF")
        self.assertIn("Teaching materials extracted", merged.summary)

        inferred = cli._merged_course({}, {"id": "folder-2", "name": "Other CF"})
        self.assertEqual(inferred.source_drive_folder_id, "folder-2")

        client = mock.Mock()
        client.list_folder_items.return_value = [
            {"mimeType": "application/vnd.google-apps.folder"},
            {"id": "f", "name": "Deck", "mimeType": "application/pdf", "webViewLink": "https://example.com"},
        ]
        materials = cli._discover_materials(client, "folder-1")
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0].title, "Deck")

    def test_backfill_dry_run_incremental_and_publish(self) -> None:
        existing = sample_course(slug="existing", folder_id="existing-folder")
        discovered_course = sample_course(slug="fresh", folder_id="folder-1")
        args = argparse.Namespace(
            limit=None,
            slug=None,
            dry_run=True,
            publish_pr=False,
            branch="codex/test",
            pr_title="PR",
            pr_body="Body",
            commit_message="Commit",
            since=None,
        )
        fake_client = mock.Mock()
        fake_client.discover_course_folders.return_value = [
            {"id": "skip-folder", "name": "Skip CF"},
            {"id": "folder-1", "name": "Fresh CF"},
        ]
        with mock.patch("automation.google_drive.DriveClient.from_env", return_value=fake_client), \
            mock.patch.object(cli, "build_paths", return_value=object()), \
            mock.patch.object(cli, "load_courses", return_value=[existing]), \
            mock.patch.object(cli, "_merged_course", side_effect=[sample_course(slug="skip", folder_id="skip-folder"), discovered_course]), \
            mock.patch.object(cli, "_discover_materials", return_value=[sample_material()]), \
            mock.patch.object(cli, "load_materials", return_value=[]), \
            mock.patch.object(cli, "render_repository", return_value=RenderResult(changed_files=["A teaching/fresh.md"])), \
            mock.patch.object(cli, "_print_json") as print_json:
            self.assertEqual(cli._backfill(args, incremental=False), 0)
            print_json.assert_called_with(
                {"action": "backfill", "courses": ["skip", "fresh"], "changed_files": ["A teaching/fresh.md"]}
            )

        args.dry_run = False
        args.publish_pr = True
        fake_client.discover_course_folders.return_value = [{"id": "folder-1", "name": "Fresh CF"}]
        with mock.patch("automation.google_drive.DriveClient.from_env", return_value=fake_client), \
            mock.patch.object(cli, "build_paths", return_value=object()), \
            mock.patch.object(cli, "load_courses", return_value=[existing]), \
            mock.patch.object(cli, "_merged_course", return_value=discovered_course), \
            mock.patch.object(cli, "_discover_materials", return_value=[sample_material()]), \
            mock.patch.object(cli, "load_materials", return_value=[]), \
            mock.patch.object(cli, "write_data"), \
            mock.patch.object(cli, "render_repository", return_value=RenderResult(changed_files=[])), \
            mock.patch.object(cli, "validate_repository", return_value=[]), \
            mock.patch.object(cli, "publish_changes", return_value=SimpleNamespace(branch="codex/test", pr_url="https://example.com/pr")), \
            mock.patch.object(cli, "_print_json") as print_json:
            self.assertEqual(cli._backfill(args, incremental=True), 0)
            print_json.assert_called_with(
                {
                    "action": "backfill",
                    "courses": ["fresh"],
                    "published_branch": "codex/test",
                    "pr_url": "https://example.com/pr",
                }
            )

    def test_backfill_validation_error_and_slug_filter(self) -> None:
        course = sample_course(slug="keep", folder_id="folder-keep")
        args = argparse.Namespace(
            limit=1,
            slug="keep",
            dry_run=False,
            publish_pr=False,
            branch="codex/test",
            pr_title="PR",
            pr_body="Body",
            commit_message="Commit",
            since=None,
        )
        fake_client = mock.Mock()
        fake_client.discover_course_folders.return_value = [
            {"id": "folder-skip", "name": "Skip CF"},
            {"id": "folder-keep", "name": "Keep CF"},
        ]
        with mock.patch("automation.google_drive.DriveClient.from_env", return_value=fake_client), \
            mock.patch.object(cli, "build_paths", return_value=object()), \
            mock.patch.object(cli, "load_courses", return_value=[]), \
            mock.patch.object(cli, "_merged_course", side_effect=[sample_course(slug="skip", folder_id="folder-skip"), course]), \
            mock.patch.object(cli, "_discover_materials", return_value=[]), \
            mock.patch.object(cli, "write_data"), \
            mock.patch.object(cli, "render_repository", return_value=RenderResult(changed_files=[])), \
            mock.patch.object(cli, "validate_repository", return_value=["broken"]):
            with self.assertRaises(ValidationError):
                cli._backfill(args, incremental=False)

    def test_build_parser_and_main_dispatch(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["courses", "plan"])
        self.assertIs(args.handler, cli.cmd_plan)
        args = parser.parse_args(["courses", "backfill", "--limit", "1", "--dry-run"])
        self.assertEqual(args.limit, 1)
        self.assertTrue(args.dry_run)

        for exc, expected in [
            (ValidationError("bad"), 1),
            (AuthConfigError("auth"), 2),
            (DiscoveryError("discover"), 3),
            (PublishError("publish"), 4),
        ]:
            parser = mock.Mock()
            parser.parse_args.return_value = argparse.Namespace(handler=mock.Mock(side_effect=exc))
            with mock.patch.object(cli, "build_parser", return_value=parser), \
                contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main([]), expected)

        parser = mock.Mock()
        parser.parse_args.return_value = argparse.Namespace(handler=lambda _: 7)
        with mock.patch.object(cli, "build_parser", return_value=parser):
            self.assertEqual(cli.main([]), 7)

    def test_cmd_backfill_and_sync_wrappers(self) -> None:
        with mock.patch.object(cli, "_backfill", return_value=11) as backfill:
            args = argparse.Namespace()
            self.assertEqual(cli.cmd_backfill(args), 11)
            backfill.assert_called_with(args, incremental=False)
            self.assertEqual(cli.cmd_sync(args), 11)
            backfill.assert_called_with(args, incremental=True)
