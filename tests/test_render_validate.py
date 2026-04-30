import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation.course_family_content import apply_generalized_course_content
from automation.config import GENERATED_HEADER, TEACHING_MARKER_END, TEACHING_MARKER_START, build_paths
from automation.data_io import load_courses, load_materials
from automation.models import Course, ExcludedMaterial, Material
from automation.rendering import (
    _academic_period_sort_value,
    _render_lecture_item,
    _render_named_list_item,
    file_diff_summary,
    inject_managed_block,
    render_course_page,
    render_teaching_block,
    should_render_course_page,
    visible_courses,
)
from automation.repository import clean_preview_repository, current_state, render_repository, write_data, write_preview_repository
from automation.syllabus import (
    _compact_family_markdown,
    _doc_text_to_markdown,
    _looks_like_admin_dump,
    _maybe_rewrite_with_openai,
    _normalize_text,
    _sheet_needs_compaction,
    _should_use_compact_family_outline,
    _tsv_to_markdown,
    render_syllabus_markdown,
    select_syllabus_material,
    syllabus_export_mime,
)
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
            subtitle="Course page for teaching materials, 22/23 (Semester A)",
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
            subtitle="Course page for teaching materials, 22/23 (Semester B)",
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
        concrete_a.manual_overrides["section_label"] = "Semester"
        concrete_b.manual_overrides["section_label"] = "Semester"
        generalized_page = render_course_page(generalized, [], courses=[generalized, concrete_a, concrete_b])
        self.assertLess(generalized_page.index("Semester B"), generalized_page.index("Semester A"))

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
        self.assertEqual(_academic_period_sort_value(Course(
            slug="manual",
            title="Manual",
            subtitle="Manual",
            institution="Unknown",
            role="Instructor",
            academic_period="TBD",
            status="active",
            source_drive_folder_id="manual",
            source_drive_folder_name="Manual CF",
            summary="Manual.",
            visibility="public",
        )), (1, 0, "tbd"))
        self.assertEqual(_render_named_list_item({"name": "Only Name"}), "* Only Name")
        self.assertEqual(_render_named_list_item({"role": "Program lead", "company": "DataNights"}), "* Program lead, DataNights")
        self.assertEqual(_render_named_list_item({}), "")
        self.assertEqual(_render_named_list_item("Plain item"), "* Plain item")
        self.assertEqual(_render_named_list_item(""), "")
        self.assertEqual(_render_lecture_item("Session 1"), ["* Session 1"])
        self.assertEqual(_render_lecture_item(""), [])
        self.assertEqual(
            _render_lecture_item({"status": "planned", "description": "Soon"}),
            ["* Untitled session (planned)", "  Soon"],
        )

        generic_summary_course = Course(
            slug="generic-25a",
            title="Generic",
            subtitle="Course page for teaching materials, 25/26 (Semester A)",
            institution="Unknown institution",
            role="Instructor",
            academic_period="25/26",
            status="active",
            source_drive_folder_id="generic-folder",
            source_drive_folder_name="Generic 25/26A CF",
            summary="Teaching materials extracted from Google Drive folder 'Generic 25/26A CF'.",
            visibility="public",
        )
        self.assertFalse(
            should_render_course_page(
                generic_summary_course,
                [
                    Material(
                        title="Week 1 Slides",
                        url="https://example.com/week-1",
                        kind="slides",
                        week=1,
                        section="Course Materials",
                        published=True,
                        sort_key="01-week-1",
                    )
                ],
            )
        )

    def test_syllabus_helpers(self) -> None:
        doc_material = Material(
            title="Course details",
            url="https://example.com/doc",
            kind="outline",
            source_file_id="doc-id",
            source_mime_type="application/vnd.google-apps.document",
            sort_key="01-doc",
        )
        docx_material = Material(
            title="Course details docx",
            url="https://example.com/docx",
            kind="syllabus",
            source_file_id="docx-id",
            source_mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            sort_key="00-docx",
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
        self.assertIsNone(syllabus_export_mime(Material(
            title="PDF outline",
            url="https://example.com/pdf",
            kind="outline",
            source_mime_type="application/pdf",
        )))
        self.assertEqual(
            render_syllabus_markdown(doc_material, "Intro\n\n• First topic\n2. Second topic\n\nhttps://example.com/form"),
            "Intro\n\n* First topic\n* Second topic",
        )
        self.assertEqual(
            render_syllabus_markdown(docx_material, "Intro\n\n• First topic"),
            "Intro\n\n* First topic",
        )
        admin_material = Material(
            title="EconML 25 - Course Moodle Website Outline and Lecturer Annoucements",
            url="https://example.com/admin",
            kind="outline",
            source_file_id="admin-id",
            source_mime_type="application/vnd.google-apps.document",
            sort_key="03-admin",
            published=False,
        )
        self.assertEqual(
            render_syllabus_markdown(admin_material, "Course Repository\nלוח הודעות\nPart 1"),
            "",
        )
        self.assertEqual(
            render_syllabus_markdown(sheet_material, "Week\tTopic\n1\tIntro\n"),
            '<table class="course-outline-table">\n'
            "  <thead>\n"
            "    <tr>\n"
            "      <th>Week</th>\n"
            "      <th>Topic</th>\n"
            "    </tr>\n"
            "  </thead>\n"
            "  <tbody>\n"
            "    <tr>\n"
            "      <td>1</td>\n"
            "      <td>Intro</td>\n"
            "    </tr>\n"
            "  </tbody>\n"
            "</table>",
        )
        data_vis_course = Course(
            slug="data-vis-25a",
            title="Data Vis",
            subtitle="Course page for teaching materials, 25/26 (Semester A)",
            institution="Tel Aviv University",
            role="Instructor",
            academic_period="25/26",
            status="active",
            source_drive_folder_id="folder",
            source_drive_folder_name="Data Vis 25/6A CF",
            summary="summary",
            visibility="public",
            course_family="data-vis",
            section="A",
        )
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            compact = render_syllabus_markdown(docx_material, "Raw doc text", course=data_vis_course)
        self.assertIn("compact-course-outline-table", compact)
        self.assertIn("Lecture", compact)
        with mock.patch("automation.syllabus.rewrite_syllabus_markdown", return_value="LLM markdown"):
            self.assertEqual(
                render_syllabus_markdown(doc_material, "Raw doc text", course=data_vis_course),
                "LLM markdown",
            )
        self.assertEqual(_normalize_text("a\r\nb\rc"), "a\nb\nc")
        self.assertEqual(render_syllabus_markdown(doc_material, "   "), "")
        low_signal_material = Material(
            title="Outline",
            url="https://example.com/low-signal",
            kind="outline",
            source_file_id="low-signal-id",
            source_mime_type="application/vnd.google-apps.document",
            sort_key="04-low-signal",
        )
        self.assertTrue(_looks_like_admin_dump(low_signal_material, "לינקים לדברים:\nfoo"))
        self.assertTrue(_should_use_compact_family_outline(data_vis_course, sheet_material, "Week\tTopic\n1\tIntro"))
        neutral_course = Course(
            slug="neutral-25a",
            title="Neutral",
            subtitle="Neutral subtitle",
            institution="Unknown institution",
            role="Instructor",
            academic_period="25/26",
            status="active",
            source_drive_folder_id="neutral-folder",
            source_drive_folder_name="Neutral 25/6A CF",
            summary="summary",
            visibility="public",
            course_family="neutral",
            section="A",
        )
        self.assertTrue(_should_use_compact_family_outline(neutral_course, sheet_material, "Done?\tWhat\tDetails"))
        self.assertFalse(_should_use_compact_family_outline(neutral_course, doc_material, "Topic list"))
        self.assertTrue(_sheet_needs_compaction("Done?\tWhat\tDetails"))
        self.assertTrue(_sheet_needs_compaction("Week \\ Axis\tA\tB\tC\tD\tE\tF"))
        self.assertFalse(_sheet_needs_compaction(""))
        self.assertEqual(render_syllabus_markdown(sheet_material, "Done?\tWhat\tDetails"), "")
        self.assertEqual(_maybe_rewrite_with_openai(neutral_course, Material(
            title="PDF outline",
            url="https://example.com/pdf",
            kind="outline",
            source_mime_type="application/pdf",
        ), "ignored"), None)
        self.assertEqual(_compact_family_markdown(neutral_course), "")
        self.assertEqual(
            render_syllabus_markdown(
                Material(
                    title="Binary syllabus",
                    url="https://example.com/bin",
                    kind="syllabus",
                    source_mime_type="application/octet-stream",
                ),
                "Some text",
            ),
            "",
        )
        self.assertEqual(_doc_text_to_markdown("https://example.com/only-link"), "")
        self.assertEqual(_doc_text_to_markdown("1. Item"), "* Item")
        budget_text = "\n".join(["one", "", "two"])
        self.assertEqual(_doc_text_to_markdown(budget_text), "one\n\ntwo")
        long_text = " ".join(f"word{i}" for i in range(260))
        self.assertTrue(_doc_text_to_markdown(long_text).endswith("..."))
        exact_budget = " ".join("word" for _ in range(250))
        self.assertEqual(_doc_text_to_markdown(exact_budget), exact_budget)
        self.assertEqual(_tsv_to_markdown(""), "")
        self.assertIn("<br>", _tsv_to_markdown("Week\tTopic\n1\tIntro\n\tMore intro"))

        self.assertIsNone(select_syllabus_material([Material(
            title="Hidden outline",
            url="https://example.com/hidden",
            kind="outline",
            source_file_id="hidden",
            source_mime_type="application/vnd.google-apps.document",
            sort_key="00-hidden",
            published=False,
        )]))
        self.assertEqual(
            render_syllabus_markdown(sheet_material, "Week\tDate\tTopic\n-\t06/01/25\tFinal Exam\n\t16/01/25\tPublishing grades!\n"),
            '<table class="course-outline-table">\n'
            "  <thead>\n"
            "    <tr>\n"
            "      <th>Week</th>\n"
            "      <th>Date</th>\n"
            "      <th>Topic</th>\n"
            "    </tr>\n"
            "  </thead>\n"
            "  <tbody>\n"
            "    <tr>\n"
            "      <td>-</td>\n"
            "      <td>06/01/25<br>16/01/25</td>\n"
            "      <td>Final Exam<br>Publishing grades!</td>\n"
            "    </tr>\n"
            "  </tbody>\n"
            "</table>",
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
        generalized_tba = render_course_page(
            Course(
                slug="orphan-generalized",
                title="Orphan Generalized",
                subtitle="Overview",
                institution="Unknown institution",
                role="Instructor",
                academic_period="TBD",
                status="active",
                source_drive_folder_id="orphan",
                source_drive_folder_name="Orphan - Generalized CF",
                summary="No iterations yet.",
                visibility="public",
                course_family="orphan",
                is_generalized=True,
            ),
            [],
            courses=[],
        )
        self.assertNotIn("## Course Iterations", generalized_tba)
        generalized_tba = render_course_page(
            Course(
                slug="orphan-generalized",
                title="Orphan Generalized",
                subtitle="Overview",
                institution="Unknown institution",
                role="Instructor",
                academic_period="TBD",
                status="active",
                source_drive_folder_id="orphan",
                source_drive_folder_name="Orphan - Generalized CF",
                summary="No iterations yet.",
                visibility="public",
                course_family="orphan",
                is_generalized=True,
            ),
            [],
            courses=[
                Course(
                    slug="orphan-generalized",
                    title="Orphan Generalized",
                    subtitle="Overview",
                    institution="Unknown institution",
                    role="Instructor",
                    academic_period="TBD",
                    status="active",
                    source_drive_folder_id="orphan",
                    source_drive_folder_name="Orphan - Generalized CF",
                    summary="No iterations yet.",
                    visibility="public",
                    course_family="orphan",
                    is_generalized=True,
                )
            ],
        )
        self.assertIn("## Course Iterations", generalized_tba)
        self.assertIn("TBA", generalized_tba)
        lectures_tba_page = render_course_page(
            Course(
                slug="lectures-tba",
                title="Lectures TBA",
                subtitle="Overview",
                institution="Unknown institution",
                role="Instructor",
                academic_period="25/26",
                status="active",
                source_drive_folder_id="lectures-tba",
                source_drive_folder_name="Lectures TBA CF",
                summary="Summary.",
                visibility="public",
                manual_overrides={"lectures_note": "Schedule coming soon."},
            ),
            [],
        )
        self.assertIn("Schedule coming soon.", lectures_tba_page)
        self.assertIn("## Lectures", lectures_tba_page)
        self.assertIn("TBA", lectures_tba_page)
        notes_only_page = render_course_page(
            Course(
                slug="notes-only",
                title="Notes Only",
                subtitle="Overview",
                institution="Unknown institution",
                role="Instructor",
                academic_period="25/26",
                status="active",
                source_drive_folder_id="notes-only",
                source_drive_folder_name="Notes Only CF",
                summary="Summary.",
                visibility="public",
            ),
            [
                Material(
                    title="Notebook",
                    url="https://example.com/notebook",
                    kind="notebook",
                    published=True,
                    section="Course Materials",
                    sort_key="01-notebook",
                    notes="Bring laptop",
                )
            ],
        )
        self.assertIn("(Bring laptop)", notes_only_page)

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
        (paths.preview_root / "stale.txt").write_text("stale", encoding="utf-8")
        preview_files = write_preview_repository(paths, courses, materials_by_slug)
        self.assertTrue((paths.preview_teaching_root / f"{courses[0].slug}.md").exists())
        self.assertTrue(paths.preview_teaching_index.exists())
        self.assertIn(paths.preview_teaching_index.as_posix(), preview_files)
        self.assertFalse((paths.preview_root / "stale.txt").exists())
        self.assertTrue(clean_preview_repository(paths))
        self.assertFalse(paths.preview_root.exists())
        self.assertFalse(clean_preview_repository(paths))

    def test_write_preview_repository_writes_excluded_material_audit(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
        excluded = [
            ExcludedMaterial(
                course_slug="econml-24",
                title="Grades Timeline",
                reason="privacy-admin",
                source_file_id="grades-1",
                url="https://example.com/grades",
                mime_type="application/vnd.google-apps.spreadsheet",
            )
        ]
        preview_files = write_preview_repository(paths, courses, materials_by_slug, excluded)
        self.assertIn(paths.preview_excluded_materials.as_posix(), preview_files)
        audit = paths.preview_excluded_materials.read_text(encoding="utf-8")
        self.assertIn("excluded_materials:", audit)
        self.assertIn("Grades Timeline", audit)
        self.assertIn("privacy-admin", audit)

    def test_suppressed_semester_pages_are_hidden_everywhere(self) -> None:
        paths = build_paths(self.repo_root)
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
        suppressed = Course(
            slug="data-vis-23b",
            title="Data Vis",
            subtitle="Course page for teaching materials, 23/24 (Semester B)",
            institution="Unknown institution",
            role="Instructor",
            academic_period="23/24",
            status="active",
            source_drive_folder_id="folder-b",
            source_drive_folder_name="Data Vis 23/24B CF",
            summary="Curated semester summary.",
            visibility="public",
            course_family="data-vis",
            section="B",
        )
        visible = Course(
            slug="data-vis-24a",
            title="Data Vis",
            subtitle="Course page for teaching materials, 24/25 (Semester A)",
            institution="Unknown institution",
            role="Instructor",
            academic_period="24/25",
            status="active",
            source_drive_folder_id="folder-a",
            source_drive_folder_name="Data Vis 24/25A CF",
            summary="Curated semester summary.",
            visibility="public",
            course_family="data-vis",
            section="A",
        )
        courses = [generalized, suppressed, visible]
        materials_by_slug = {
            "data-vis": [
                Material(
                    title="Week 1 Slides",
                    url="https://example.com/shared",
                    kind="slides",
                    week=1,
                    section="Course Materials",
                    published=True,
                    sort_key="01-shared",
                )
            ],
            "data-vis-23b": [
                Material(
                    title="Course Syllabus",
                    url="https://example.com/syllabus",
                    kind="syllabus",
                    published=True,
                    section="Course Outline",
                    sort_key="00-syllabus",
                )
            ],
            "data-vis-24a": [
                Material(
                    title="Week 1 Slides",
                    url="https://example.com/week-1",
                    kind="slides",
                    week=1,
                    section="Course Materials",
                    published=True,
                    sort_key="01-week-1",
                )
            ],
        }

        self.assertEqual(
            [course.slug for course in visible_courses(courses, materials_by_slug)],
            ["data-vis"],
        )

        render_repository(paths, courses, materials_by_slug, dry_run=False)
        self.assertTrue((paths.teaching_root / "data-vis.md").exists())
        self.assertTrue((paths.teaching_root / "data-vis-24a.md").exists())
        self.assertFalse((paths.teaching_root / "data-vis-23b.md").exists())

        generalized_page = (paths.teaching_root / "data-vis.md").read_text(encoding="utf-8")
        self.assertIn("/teaching/data-vis-24a", generalized_page)
        self.assertNotIn("/teaching/data-vis-23b", generalized_page)

        teaching_index = paths.teaching_index.read_text(encoding="utf-8")
        self.assertIn("/teaching/data-vis", teaching_index)
        self.assertNotIn("/teaching/data-vis-24a", teaching_index)
        self.assertNotIn("/teaching/data-vis-23b", teaching_index)

        self.assertEqual(validate_generated_files(paths, courses, materials_by_slug), [])

    def test_apply_generalized_course_content_leaves_unknown_family_unchanged(self) -> None:
        course = Course(
            slug="unknown",
            title="Unknown",
            subtitle="Subtitle",
            institution="Unknown institution",
            role="Instructor",
            academic_period="TBD",
            status="active",
            source_drive_folder_id="unknown",
            source_drive_folder_name="Unknown - Generalized CF",
            summary="Summary.",
            visibility="public",
            course_family="unknown-family",
            is_generalized=True,
        )
        self.assertIs(apply_generalized_course_content(course), course)

    def test_validate_generated_files_reports_missing_markers(self) -> None:
        paths = build_paths(self.repo_root)
        courses = load_courses(paths)
        materials_by_slug = {course.slug: load_materials(paths, course.slug) for course in courses}
        render_repository(paths, courses, materials_by_slug, dry_run=False)
        paths.teaching_index.write_text("no managed markers here", encoding="utf-8")
        errors = validate_generated_files(paths, courses, materials_by_slug)
        self.assertTrue(any("invalid managed block markers" in error for error in errors))

    def test_validate_generated_files_rejects_generated_suppressed_page(self) -> None:
        paths = build_paths(self.repo_root)
        suppressed = Course(
            slug="data-vis-23b",
            title="Data Vis",
            subtitle="Course page for teaching materials, 23/24 (Semester B)",
            institution="Unknown institution",
            role="Instructor",
            academic_period="23/24",
            status="active",
            source_drive_folder_id="folder-b",
            source_drive_folder_name="Data Vis 23/24B CF",
            summary="Curated semester summary.",
            visibility="public",
            course_family="data-vis",
            section="B",
        )
        materials_by_slug = {
            suppressed.slug: [
                Material(
                    title="Course Syllabus",
                    url="https://example.com/syllabus",
                    kind="syllabus",
                    published=True,
                    section="Course Outline",
                    sort_key="00-syllabus",
                )
            ]
        }
        target = paths.teaching_root / f"{suppressed.slug}.md"
        target.write_text(
            "\n".join(
                [
                    "---",
                    "layout: page",
                    "title: Suppressed",
                    "---",
                    "",
                    GENERATED_HEADER,
                    "",
                    "stale suppressed page",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        errors = validate_generated_files(paths, [suppressed], materials_by_slug)
        self.assertTrue(any("suppressed course page should not be generated" in error for error in errors))
