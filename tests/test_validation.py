import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation.config import TEACHING_MARKER_END, TEACHING_MARKER_START, build_paths
from automation.data_io import load_courses, load_materials, save_courses
from automation.models import Material
from automation.repository import render_repository
from automation.validation import (
    _missing_fields,
    _supported_google_pattern,
    _valid_url,
    validate_courses,
    validate_generated_files,
    validate_internal_links,
    validate_materials,
    validate_public_page_data,
    validate_repository,
)


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
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
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

    def test_validation_helpers_and_error_paths(self) -> None:
        self.assertEqual(_missing_fields({"a": 1}, ["a", "b"]), ["b"])
        self.assertEqual(_missing_fields({"a": "   ", "b": None}, ["a", "b"]), ["a", "b"])
        self.assertEqual(_missing_fields({"week": None}, ["week"]), [])
        self.assertTrue(_valid_url("https://example.com"))
        self.assertFalse(_valid_url("not-a-url"))
        self.assertTrue(_supported_google_pattern("https://example.com/page"))
        self.assertTrue(_supported_google_pattern("https://docs.google.com/presentation/d/abc/edit"))
        self.assertFalse(_supported_google_pattern("https://docs.google.com/unsupported/path"))
        self.assertTrue(_supported_google_pattern("https://drive.google.com/file/d/abc/view"))
        self.assertFalse(_supported_google_pattern("https://drive.google.com/open?id=abc"))

        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        course = courses[0]
        course.visibility = "private"
        course.syllabus_url = "not-a-url"
        course.slug = ""
        errors = validate_courses([course])
        self.assertTrue(any("only public courses are supported" in error for error in errors))
        self.assertTrue(any("invalid syllabus_url" in error for error in errors))
        self.assertTrue(any("Course slug must be non-empty" in error for error in errors))
        course.slug = "Not Valid"
        errors = validate_courses([course])
        self.assertTrue(any("invalid slug format" in error for error in errors))
        missing_course = mock.Mock(slug="broken-course", visibility="public", syllabus_url="")
        missing_course.to_dict.return_value = {}
        errors = validate_courses([missing_course])
        self.assertTrue(any("missing course fields" in error for error in errors))

        material = Material(title="Bad", url="notaurl", kind="slides", published=True)
        errors = validate_materials("course", [material])
        self.assertTrue(any("invalid URL" in error for error in errors))
        missing_material = mock.Mock(title="broken-material", url="", published=False)
        missing_material.to_dict.return_value = {}
        errors = validate_materials("course", [missing_material])
        self.assertTrue(any("missing material fields" in error for error in errors))
        blank_material = mock.Mock(title="broken-material", url="", published=False)
        blank_material.to_dict.return_value = {
            "title": "  ",
            "url": "",
            "kind": "slides",
            "week": 1,
            "section": "Course Materials",
            "source_file_id": "x",
            "source_mime_type": "application/pdf",
            "published": False,
            "sort_key": "01",
            "notes": "",
        }
        errors = validate_materials("course", [blank_material])
        self.assertTrue(any("missing material fields" in error for error in errors))

        google_material = Material(
            title="Bad google",
            url="https://docs.google.com/unsupported/path",
            kind="slides",
            published=False,
            section="Course Materials",
            sort_key="01",
            source_file_id="x",
            source_mime_type="application/pdf",
            notes="",
        )
        errors = validate_materials("course", [google_material])
        self.assertTrue(any("unsupported Google URL pattern" in error for error in errors))

        errors = validate_public_page_data(
            "writing",
            {
                "front_matter": [],
                "selected": {"items": [{"anchor": "missing-anchor", "title": "Missing"}]},
                "writing": [{"anchor": "Bad Anchor", "markdown": ""}],
            },
        )
        self.assertTrue(any("front_matter must be a mapping" in error for error in errors))
        self.assertTrue(any("invalid anchor format" in error for error in errors))
        self.assertTrue(any("missing markdown" in error for error in errors))
        self.assertTrue(any("points to missing anchor" in error for error in errors))

        errors = validate_public_page_data(
            "projects",
            {
                "front_matter": {"redirect_from": ["code.html"]},
                "selected": {"items": []},
                "groups": [],
            },
        )
        self.assertTrue(any("redirect_from path must start with '/'" in error for error in errors))

    def test_generated_file_and_internal_link_validation(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}

        target = paths.teaching_root / f"{courses[0].slug}.md"
        target.unlink()
        errors = validate_generated_files(paths, courses, materials_by_slug)
        self.assertTrue(any("Missing generated page" in error for error in errors))

        render_repository(paths, courses, materials_by_slug, dry_run=False)
        target.write_text("broken", encoding="utf-8")
        errors = validate_generated_files(paths, courses, materials_by_slug)
        self.assertTrue(any("missing generated file header" in error or "stale generated content" in error for error in errors))

        render_repository(paths, courses, materials_by_slug, dry_run=False)
        paths.teaching_index.write_text("no links", encoding="utf-8")
        errors = validate_internal_links(paths, courses[:1])
        self.assertTrue(any("missing internal link" in error for error in errors))
        paths.teaching_index.write_text(
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
        render_repository(paths, courses, materials_by_slug, dry_run=False)
        (paths.teaching_root / f"{courses[0].slug}.md").unlink()
        errors = validate_internal_links(paths, courses[:1])
        self.assertTrue(any("Internal link target missing" in error for error in errors))
