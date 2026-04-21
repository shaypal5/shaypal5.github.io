import os
import tempfile
import unittest
from pathlib import Path

from automation.config import AuthConfigError, TOKEN_URI_DEFAULT, build_paths, drive_roots, repo_root, required_google_env
from automation.data_io import _read_yaml, load_courses, load_materials, save_courses, save_materials
from automation.models import Course, Material


class ConfigDataIoTests(unittest.TestCase):
    def test_repo_root_and_build_paths(self) -> None:
        root = repo_root()
        self.assertTrue((root / "automation").exists())
        paths = build_paths(Path("/tmp/example"))
        self.assertEqual(paths.teaching_index.as_posix(), "/tmp/example/teaching.md")

    def test_required_google_env_and_drive_roots(self) -> None:
        keys = [
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GOOGLE_OAUTH_REFRESH_TOKEN",
            "GOOGLE_OAUTH_TOKEN_URI",
            "GOOGLE_DRIVE_ROOTS",
        ]
        old = {key: os.environ.get(key) for key in keys}
        try:
            for key in keys:
                os.environ.pop(key, None)
            with self.assertRaises(AuthConfigError):
                required_google_env()
            self.assertEqual(drive_roots(), [])

            os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "id"
            os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = "secret"
            os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"] = "refresh"
            env = required_google_env()
            self.assertEqual(env["GOOGLE_OAUTH_TOKEN_URI"], TOKEN_URI_DEFAULT)

            os.environ["GOOGLE_OAUTH_TOKEN_URI"] = " https://custom/token "
            os.environ["GOOGLE_DRIVE_ROOTS"] = " root-a, root-b ,, "
            env = required_google_env()
            self.assertEqual(env["GOOGLE_OAUTH_TOKEN_URI"], "https://custom/token")
            self.assertEqual(drive_roots(), ["root-a", "root-b"])
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_read_and_write_yaml_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = build_paths(root)
            self.assertEqual(_read_yaml(root / "missing.yml"), {})

            bad = root / "bad.yml"
            bad.write_text("- not-a-mapping\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                _read_yaml(bad)

            course = Course(
                slug="z-course",
                title="Title",
                subtitle="Subtitle",
                institution="Inst",
                role="Instructor",
                academic_period="2025",
                status="active",
                source_drive_folder_id="folder",
                source_drive_folder_name="Folder CF",
                summary="Summary",
                visibility="public",
            )
            save_courses(paths, [course])
            self.assertEqual(load_courses(paths)[0].slug, "z-course")

            materials = [
                Material(
                    title="B",
                    url="https://example.com/b",
                    kind="slides",
                    week=2,
                    section="Course Materials",
                    source_file_id="2",
                    source_mime_type="application/pdf",
                    published=True,
                    sort_key="02-b",
                    notes="",
                ),
                Material(
                    title="A",
                    url="https://example.com/a",
                    kind="slides",
                    week=1,
                    section="Course Materials",
                    source_file_id="1",
                    source_mime_type="application/pdf",
                    published=True,
                    sort_key="01-a",
                    notes="",
                ),
            ]
            save_materials(paths, "z-course", materials)
            loaded = load_materials(paths, "z-course")
            self.assertEqual([item.title for item in loaded], ["A", "B"])
