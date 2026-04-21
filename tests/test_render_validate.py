import shutil
import tempfile
import unittest
from pathlib import Path

from automation.config import TEACHING_MARKER_END, TEACHING_MARKER_START, build_paths
from automation.data_io import load_courses, load_materials
from automation.repository import render_repository
from automation.validation import validate_repository


class RenderValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        source_root = Path(__file__).resolve().parents[1]
        shutil.copytree(source_root / "data", self.repo_root / "data")
        shutil.copytree(source_root / "teaching", self.repo_root / "teaching")
        (self.repo_root / "teaching.md").write_text(
            "\n".join(
                [
                    "---",
                    "layout: page",
                    "title: Teaching",
                    "---",
                    "",
                    "Intro text.",
                    "",
                    TEACHING_MARKER_START,
                    "old",
                    TEACHING_MARKER_END,
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_render_and_validate(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
        render_repository(paths, courses, materials_by_slug, dry_run=False)
        self.assertEqual(validate_repository(paths), [])


if __name__ == "__main__":
    unittest.main()
