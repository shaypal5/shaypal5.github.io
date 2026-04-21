import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation.config import GENERATED_HEADER, TEACHING_MARKER_END, TEACHING_MARKER_START, build_paths
from automation.data_io import load_courses, load_materials
from automation.models import Material
from automation.rendering import file_diff_summary, inject_managed_block, render_course_page, render_teaching_block
from automation.repository import current_state, render_repository, write_data
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

    def test_render_helpers_and_current_state(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
        state_courses, state_materials = current_state(paths)
        self.assertEqual(len(state_courses), len(courses))
        self.assertIn("bigdata22", state_materials)

        rendered = render_teaching_block(courses)
        self.assertIn(TEACHING_MARKER_START, rendered)
        self.assertIn(TEACHING_MARKER_END, rendered)

        updated = inject_managed_block(paths.teaching_index.read_text(encoding="utf-8"), rendered)
        self.assertIn("#### Courses", updated)
        with self.assertRaises(ValueError):
            inject_managed_block("no markers here", rendered)

        course = courses[0]
        materials = materials_by_slug[course.slug] + [
            Material(
                title="Hidden draft",
                url="https://example.com/private",
                kind="resource",
                published=False,
                section="Course Materials",
                sort_key="10-hidden-draft",
            )
        ]
        page = render_course_page(course, materials)
        self.assertIn(GENERATED_HEADER, page)
        self.assertNotIn("Hidden draft", page)

        empty_course_page = render_course_page(courses[1], [])
        self.assertIn("TBA", empty_course_page)

        target = self.repo_root / "teaching" / "new-course.md"
        self.assertTrue(file_diff_summary(target, "content").startswith("A "))
        target.write_text("content", encoding="utf-8")
        self.assertIsNone(file_diff_summary(target, "content"))
        self.assertTrue(file_diff_summary(target, "changed").startswith("M "))

    def test_write_data_delegates_to_save_helpers(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
        with mock.patch("automation.repository.save_courses") as save_courses, \
            mock.patch("automation.repository.save_materials") as save_materials:
            write_data(paths, courses, materials_by_slug)
            save_courses.assert_called_once_with(paths, courses)
            self.assertEqual(save_materials.call_count, len(materials_by_slug))
