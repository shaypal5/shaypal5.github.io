import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation.config import GENERATED_HEADER, TEACHING_MARKER_END, TEACHING_MARKER_START, build_paths
from automation.data_io import load_courses, load_materials
from automation.models import Course, Material
from automation.rendering import file_diff_summary, inject_managed_block, render_course_page, render_teaching_block, visible_courses
from automation.repository import clean_preview_repository, current_state, render_repository, write_data, write_preview_repository
from automation.syllabus import render_syllabus_markdown, select_syllabus_material, syllabus_export_mime
from automation.validation import validate_generated_files, validate_repository


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
        orphan_page = paths.teaching_root / "orphan-generated.md"
        orphan_page.write_text(
            "\n".join(
                [
                    "---",
                    "layout: page",
                    "title: Orphan",
                    "---",
                    "",
                    GENERATED_HEADER,
                    "",
                    "old",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        render_repository(paths, courses, materials_by_slug, dry_run=False)
        self.assertEqual(validate_repository(paths), [])
        self.assertFalse(orphan_page.exists())
        bigdata_page = (paths.teaching_root / "bigdata22.md").read_text(encoding="utf-8")
        self.assertLess(
            bigdata_page.index("TA Session #1: Intro to SparkSQL - Google Slides"),
            bigdata_page.index("TA Session #1: Exercise Notebook"),
        )

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

        general_page = render_course_page(
            course,
            [
                Material(
                    title="Week 1 slide deck",
                    url="https://example.com/week-1",
                    kind="slides",
                    week=1,
                    section="Course Materials",
                    published=True,
                    sort_key="01-week-1",
                ),
                Material(
                    title="General syllabus handout",
                    url="https://example.com/general",
                    kind="resource",
                    week=None,
                    section="Course Materials",
                    published=True,
                    sort_key="00-general",
                )
            ],
        )
        self.assertIn("### General Materials", general_page)

        empty_course_page = render_course_page(courses[0], [])
        self.assertIn("TBA", empty_course_page)

        override_course = Course(
            slug="datanights23",
            title="Managing Data Science Teams @ DataNights",
            subtitle="Cohort 2, Summer 2023",
            institution="DataNights",
            role="Instructor",
            academic_period="23'",
            status="archived",
            source_drive_folder_id="manual-datanights23",
            source_drive_folder_name="DS Mgmt - Cohort #2",
            summary="Second cohort summary.",
            visibility="public",
            syllabus_url="https://example.com/syllabus",
            manual_overrides={
                "iteration_label": "Cohort 2 · Summer 2023",
                "opening_paragraph": "This cohort ran weekly in Tel Aviv.",
                "organizing_team": [
                    {"name": "Shay Palachy Affek", "role": "Program lead", "company": "DataNights / DataHack"}
                ],
                "lectures": [
                    {
                        "title": "Make It Worth",
                        "speaker": "Inbal Budowski-Tal",
                        "description": "On getting ML into production.",
                    }
                ],
                "syllabus_markdown": "* Week 1: Foundations\n* Week 2: Hiring",
                "hide_empty_materials": True,
            },
        )
        override_page = render_course_page(override_course, [])
        self.assertIn("## Organizing Team", override_page)
        self.assertIn("## Lectures", override_page)
        self.assertIn("Make It Worth - Inbal Budowski-Tal", override_page)
        self.assertIn("This cohort ran weekly in Tel Aviv.", override_page)
        self.assertIn("* Week 1: Foundations", override_page)
        self.assertNotIn("## Course Materials", override_page)

        outline_page = render_course_page(
            override_course,
            [
                Material(
                    title="Course Outline",
                    url="https://example.com/outline",
                    kind="outline",
                    published=True,
                    section="Course Outline",
                    sort_key="00-outline",
                )
            ],
        )
        self.assertEqual(outline_page.count("Course Outline"), 1)

        generalized = Course(
            slug="data-vis",
            title="Data Vis",
            subtitle="Shared materials",
            institution="Unknown institution",
            role="Instructor",
            academic_period="TBD",
            status="active",
            source_drive_folder_id="generalized-folder",
            source_drive_folder_name="Data Vis - Generalized CF",
            summary="Shared materials across iterations.",
            visibility="public",
            course_family="data-vis",
            is_generalized=True,
        )
        concrete_a = Course(
            slug="data-vis-22a",
            title="Data Vis",
            subtitle="Course page for teaching materials, 22/23 (Section A)",
            institution="Unknown institution",
            role="Instructor",
            academic_period="22/23",
            status="active",
            source_drive_folder_id="folder-a",
            source_drive_folder_name="Data Vis 22/23A CF",
            summary="A section.",
            visibility="public",
            course_family="data-vis",
            section="A",
            manual_overrides={"iteration_sort_key": "02"},
        )
        concrete_b = Course(
            slug="data-vis-22b",
            title="Data Vis",
            subtitle="Course page for teaching materials, 22/23 (Section B)",
            institution="Unknown institution",
            role="Instructor",
            academic_period="22/23",
            status="active",
            source_drive_folder_id="folder-b",
            source_drive_folder_name="Data Vis 22/23B CF",
            summary="B section.",
            visibility="public",
            course_family="data-vis",
            section="B",
            manual_overrides={"iteration_sort_key": "01"},
        )
        generalized_page = render_course_page(
            generalized,
            [
                Material(
                    title="Lecture 1 Slides",
                    url="https://example.com/slides",
                    kind="slides",
                    week=1,
                    section="Course Materials",
                    published=True,
                    sort_key="01-slides",
                    description="Week 1 lecture slides",
                )
            ],
            courses=[generalized, concrete_a, concrete_b],
        )
        self.assertIn("## Course Iterations", generalized_page)
        self.assertIn("/teaching/data-vis-22a", generalized_page)
        self.assertIn("/teaching/data-vis-22b", generalized_page)
        self.assertIn("## Shared Course Materials", generalized_page)
        self.assertIn("Week 1 lecture slides", generalized_page)
        self.assertLess(generalized_page.index("Section B"), generalized_page.index("Section A"))

        ordered_courses = visible_courses(
            [
                Course(
                    slug="data-vis",
                    title="Data Vis",
                    subtitle="Shared materials",
                    institution="Unknown institution",
                    role="Instructor",
                    academic_period="TBD",
                    status="active",
                    source_drive_folder_id="generalized-folder",
                    source_drive_folder_name="Data Vis - Generalized CF",
                    summary="Shared materials across iterations.",
                    visibility="public",
                    course_family="data-vis",
                    is_generalized=True,
                ),
                Course(
                    slug="deep-learning",
                    title="Deep Learning",
                    subtitle="Shared materials",
                    institution="Unknown institution",
                    role="Instructor",
                    academic_period="TBD",
                    status="active",
                    source_drive_folder_id="deep-learning-folder",
                    source_drive_folder_name="Deep Learning - Generalized CF",
                    summary="Deep Learning summary.",
                    visibility="public",
                    course_family="deep-learning",
                    is_generalized=True,
                ),
                Course(
                    slug="new-course",
                    title="New Course",
                    subtitle="Course home",
                    institution="Unknown institution",
                    role="Instructor",
                    academic_period="26/27",
                    status="active",
                    source_drive_folder_id="new-course-folder",
                    source_drive_folder_name="New Course 26/7 CF",
                    summary="New course summary.",
                    visibility="public",
                    course_family="new-course",
                    is_generalized=True,
                ),
            ]
        )
        self.assertEqual([course.slug for course in ordered_courses], ["deep-learning", "data-vis", "new-course"])

    def test_syllabus_helpers(self) -> None:
        doc_material = Material(
            title="Course details",
            url="https://example.com/doc",
            kind="outline",
            source_file_id="doc-id",
            source_mime_type="application/vnd.google-apps.document",
            sort_key="01-doc",
        )
        sheet_material = Material(
            title="Outline sheet",
            url="https://example.com/sheet",
            kind="outline",
            source_file_id="sheet-id",
            source_mime_type="application/vnd.google-apps.spreadsheet",
            sort_key="02-sheet",
        )
        self.assertIs(select_syllabus_material([sheet_material, doc_material]), doc_material)
        self.assertEqual(syllabus_export_mime(doc_material), "text/plain")
        self.assertEqual(syllabus_export_mime(sheet_material), "text/tab-separated-values")
        self.assertEqual(
            render_syllabus_markdown(doc_material, "Intro\n\n• First topic\n2. Second topic\n"),
            "Intro\n\n* First topic\n* Second topic",
        )
        self.assertEqual(
            render_syllabus_markdown(sheet_material, "Week\tTopic\n1\tIntro\n"),
            "| Week | Topic |\n| --- | --- |\n| 1 | Intro |",
        )

        generalized_without_materials = render_course_page(
            Course(
                slug="datanights",
                title="Managing Data Science Teams @ DataNights",
                subtitle="Program overview",
                institution="DataNights",
                role="Instructor",
                academic_period="TBD",
                status="active",
                source_drive_folder_id="manual-datanights-program",
                source_drive_folder_name="DS Mgmt Program",
                summary="Program summary.",
                visibility="public",
                course_family="datanights",
                is_generalized=True,
                manual_overrides={"hide_empty_materials": True},
            ),
            [],
            courses=[
                Course(
                    slug="datanights",
                    title="Managing Data Science Teams @ DataNights",
                    subtitle="Program overview",
                    institution="DataNights",
                    role="Instructor",
                    academic_period="TBD",
                    status="active",
                    source_drive_folder_id="manual-datanights-program",
                    source_drive_folder_name="DS Mgmt Program",
                    summary="Program summary.",
                    visibility="public",
                    course_family="datanights",
                    is_generalized=True,
                    manual_overrides={"hide_empty_materials": True},
                ),
                Course(
                    slug="datanights22",
                    title="Managing Data Science Teams @ DataNights",
                    subtitle="Cohort 1",
                    institution="DataNights",
                    role="Instructor",
                    academic_period="22'",
                    status="archived",
                    source_drive_folder_id="manual-datanights22",
                    source_drive_folder_name="DS Mgmt - Cohort #1",
                    summary="Cohort 1.",
                    visibility="public",
                    course_family="datanights",
                    manual_overrides={"iteration_label": "Cohort 1 · Summer 2022"},
                ),
            ],
        )
        self.assertIn("## Course Iterations", generalized_without_materials)
        self.assertIn("Cohort 1 · Summer 2022", generalized_without_materials)
        self.assertNotIn("## Shared Course Materials", generalized_without_materials)

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

    def test_write_and_clean_preview_repository(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
        preview_files = write_preview_repository(paths, courses, materials_by_slug)
        self.assertTrue((paths.preview_teaching_root / f"{courses[0].slug}.md").exists())
        self.assertTrue(paths.preview_teaching_index.exists())
        self.assertIn(paths.preview_teaching_index.as_posix(), preview_files)
        self.assertTrue(clean_preview_repository(paths))
        self.assertFalse(paths.preview_root.exists())
        self.assertFalse(clean_preview_repository(paths))

    def test_validate_generated_files_reports_missing_markers(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
        render_repository(paths, courses, materials_by_slug, dry_run=False)
        paths.teaching_index.write_text("no managed markers here", encoding="utf-8")
        errors = validate_generated_files(paths, courses, materials_by_slug)
        self.assertTrue(any("invalid managed block markers" in error for error in errors))
