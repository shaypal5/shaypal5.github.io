import shutil
import tempfile
import unittest
from pathlib import Path

from automation.config import TEACHING_MARKER_END, TEACHING_MARKER_START, build_paths
from automation.data_io import load_courses, save_courses
from automation.repository import render_repository
from automation.validation import validate_repository


class ValidationTests(unittest.TestCase):
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
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: [] for course in courses}
        render_repository(paths, courses, materials_by_slug, dry_run=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_duplicate_slugs_fail_validation(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        courses[1].slug = courses[0].slug
        save_courses(paths, courses)
        errors = validate_repository(paths)
        self.assertTrue(any("Duplicate course slug" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
