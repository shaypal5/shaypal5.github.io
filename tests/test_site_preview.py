import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation.config import build_paths
from automation.site_preview import build_preview_site, prepare_preview_site, serve_preview_site


class SitePreviewTests(unittest.TestCase):
    def test_prepare_preview_site_requires_preview_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_paths(Path(tmp))
            with self.assertRaises(FileNotFoundError):
                prepare_preview_site(paths)

    def test_prepare_build_and_serve_preview_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            paths = build_paths(repo_root)
            (repo_root / "teaching").mkdir(parents=True, exist_ok=True)
            (repo_root / "assets").mkdir(parents=True, exist_ok=True)
            (repo_root / "index.md").write_text("# Home\n", encoding="utf-8")
            paths.teaching_index.write_text("tracked teaching index", encoding="utf-8")
            paths.preview_teaching_root.mkdir(parents=True, exist_ok=True)
            paths.preview_teaching_index.write_text("preview teaching index", encoding="utf-8")
            (paths.preview_teaching_root / "course-a.md").write_text("preview page", encoding="utf-8")
            paths.preview_site_source_root.mkdir(parents=True, exist_ok=True)
            (paths.preview_site_source_root / "stale.txt").write_text("stale", encoding="utf-8")
            paths.preview_site_build_root.mkdir(parents=True, exist_ok=True)
            (paths.preview_site_build_root / "old.txt").write_text("old", encoding="utf-8")

            source_root, build_root = prepare_preview_site(paths)
            self.assertEqual(source_root, paths.preview_site_source_root)
            self.assertEqual(build_root, paths.preview_site_build_root)
            self.assertFalse((paths.preview_site_source_root / "stale.txt").exists())
            self.assertFalse((paths.preview_site_build_root / "old.txt").exists())
            self.assertEqual((paths.preview_site_source_root / "teaching.md").read_text(encoding="utf-8"), "preview teaching index")
            self.assertEqual((paths.preview_site_source_root / "teaching" / "course-a.md").read_text(encoding="utf-8"), "preview page")
            self.assertTrue((paths.preview_site_source_root / "index.md").exists())

            with mock.patch("automation.site_preview.subprocess.run") as run:
                built_source, built_root = build_preview_site(paths, bundle_command="bundle")
            self.assertEqual((built_source, built_root), (paths.preview_site_source_root, paths.preview_site_build_root))
            self.assertEqual(
                run.call_args.args[0],
                [
                    "bundle",
                    "exec",
                    "jekyll",
                    "build",
                    "--source",
                    str(paths.preview_site_source_root),
                    "--destination",
                    str(paths.preview_site_build_root),
                ],
            )

            with mock.patch("automation.site_preview.subprocess.run") as run:
                served_source, served_root = serve_preview_site(paths, host="0.0.0.0", port=4010, bundle_command="bundle")
            self.assertEqual((served_source, served_root), (paths.preview_site_source_root, paths.preview_site_build_root))
            self.assertEqual(
                run.call_args.args[0],
                [
                    "bundle",
                    "exec",
                    "jekyll",
                    "serve",
                    "--source",
                    str(paths.preview_site_source_root),
                    "--destination",
                    str(paths.preview_site_build_root),
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "4010",
                ],
            )
