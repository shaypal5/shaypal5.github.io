import unittest

from automation.models import Course
from automation.naming import (
    classify_material_kind,
    classify_material_exclusion,
    infer_course_from_folder,
    infer_section,
    infer_sort_key,
    infer_week,
    is_valid_course_folder_name,
    material_from_drive_item,
    normalize_material_title,
    parse_course_folder_name,
    should_descend_into_material_folder,
    should_publish_material,
    slugify,
)
from automation.course_family_content import apply_concrete_course_content


class NamingTests(unittest.TestCase):
    def test_parse_course_folder_name(self) -> None:
        parsed = parse_course_folder_name("Intro to ML @ MTA 25 CF")
        self.assertEqual(parsed["institution"], "The Academic College of Tel Aviv-Yaffo")
        self.assertEqual(parsed["academic_period"], "25")
        self.assertEqual(parsed["title"], "Intro to ML")
        self.assertTrue(parsed["slug"].startswith("intro-to-ml"))

    def test_parse_course_folder_name_with_academic_range_and_section(self) -> None:
        parsed = parse_course_folder_name("Data Vis 22/23A CF")
        self.assertEqual(parsed["title"], "Data Vis")
        self.assertEqual(parsed["academic_period"], "22/23")
        self.assertEqual(parsed["slug"], "data-vis-22a")
        self.assertEqual(parsed["course_family"], "data-vis")
        self.assertEqual(parsed["section"], "A")
        self.assertFalse(parsed["is_generalized"])
        self.assertIn("Semester A", parsed["subtitle"])

    def test_parse_course_folder_name_generalized_without_period(self) -> None:
        parsed = parse_course_folder_name("Data Vis - Generalized CF")
        self.assertEqual(parsed["title"], "Data Vis")
        self.assertEqual(parsed["academic_period"], "TBD")
        self.assertEqual(parsed["slug"], "data-vis")
        self.assertTrue(parsed["is_generalized"])

    def test_parse_course_folder_name_short_second_year(self) -> None:
        parsed = parse_course_folder_name("Data Vis 23/4B CF")
        self.assertEqual(parsed["academic_period"], "23/24")
        self.assertEqual(parsed["slug"], "data-vis-23b")
        self.assertIn("Semester B", parsed["subtitle"])

    def test_parse_course_folder_name_ta_and_unknown_institution(self) -> None:
        parsed = parse_course_folder_name("TA Deep Learning Bootcamp 2024 CF")
        self.assertEqual(parsed["role"], "Teaching Assistant")
        self.assertEqual(parsed["institution"], "Unknown institution")
        self.assertEqual(parsed["academic_period"], "24")

    def test_parse_course_folder_name_does_not_use_internal_numeric_codes_as_year(self) -> None:
        parsed = parse_course_folder_name("ML 101 Workshop CF")
        self.assertEqual(parsed["title"], "ML 101 Workshop")
        self.assertEqual(parsed["academic_period"], "TBD")

    def test_slugify_and_infer_course(self) -> None:
        self.assertEqual(slugify("Café & ML"), "cafe-ml")
        course = infer_course_from_folder("folder-1", "DataNights Leadership 24 CF")
        self.assertIsInstance(course, Course)
        self.assertEqual(course.source_drive_folder_id, "folder-1")
        self.assertEqual(course.visibility, "public")
        generalized = infer_course_from_folder("folder-2", "Data Vis - Generalized CF")
        self.assertTrue(generalized.is_generalized)
        self.assertEqual(generalized.course_family, "data-vis")
        datavis = infer_course_from_folder("folder-3", "Data Vis 22/23A CF")
        self.assertEqual(datavis.manual_overrides["section_label"], "Semester")
        self.assertIn("(Semester A)", datavis.subtitle)

    def test_classify_material_kind(self) -> None:
        self.assertEqual(classify_material_kind("Course Syllabus", "application/pdf"), "syllabus")
        self.assertEqual(classify_material_kind("סילבוס - כריית טקסט.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), "syllabus")
        self.assertEqual(classify_material_kind("Data Vis 2022 - Outline", "application/vnd.google-apps.spreadsheet"), "outline")
        self.assertEqual(classify_material_kind("קורס ויזואליזציה - פרטים", "application/vnd.google-apps.document"), "outline")
        self.assertEqual(
            classify_material_kind("Week 2 - Lecture Slides", "application/vnd.google-apps.presentation"),
            "slides",
        )
        self.assertEqual(classify_material_kind("S0: Course Intro", "application/vnd.google-apps.presentation"), "slides")
        self.assertEqual(classify_material_kind("Notebook.ipynb", "text/plain"), "notebook")
        self.assertEqual(classify_material_kind("Exercise 1", "text/plain"), "exercise")
        self.assertEqual(classify_material_kind("Solution 1", "text/plain"), "solution")
        self.assertEqual(classify_material_kind("Poll Form", "text/plain"), "form")
        self.assertEqual(classify_material_kind("Course Survey", "text/plain"), "form")
        self.assertEqual(
            classify_material_kind("Results", "application/vnd.google-apps.spreadsheet"),
            "sheet",
        )
        self.assertEqual(classify_material_kind("Reference URL", "text/plain"), "resource")

    def test_valid_course_folder_name_and_publish_rules(self) -> None:
        self.assertTrue(is_valid_course_folder_name("Data Vis 22/23A CF"))
        self.assertFalse(is_valid_course_folder_name("Data Vis 22/23A Cf"))
        self.assertFalse(should_publish_material("Course Exercise 1", "exercise", is_generalized_course=False))
        self.assertFalse(should_publish_material("Solution Notebook", "solution", is_generalized_course=False))
        self.assertFalse(should_publish_material("Student Feedback Notes", "resource", is_generalized_course=False))
        self.assertFalse(should_publish_material("Slides from Inbal", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("Student Survey Results", "resource", is_generalized_course=False))
        self.assertFalse(should_publish_material("שאלון קורס", "resource", is_generalized_course=False))
        self.assertFalse(should_publish_material("לוח שנה תשפד - לוח 3.pdf", "resource", is_generalized_course=False))
        self.assertFalse(should_publish_material("NN_Course_Project_Presentation_TC_YH.pptx", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("random forests - presentation.pptx", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("lec5_slides.pptx", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("הקלות.pptx", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("EconML 25 - Course Moodle Website Outline and Lecturer Annoucements", "outline", is_generalized_course=False))
        self.assertFalse(should_publish_material("slides.pptx", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("TBA", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("HEx2 — Tableau Charts", "slides", is_generalized_course=False))
        self.assertFalse(should_publish_material("CEx1 - Tableau's Interface", "slides", is_generalized_course=False))
        self.assertTrue(should_publish_material("Week 1 slides", "slides", is_generalized_course=False))
        self.assertTrue(should_publish_material("Course Syllabus", "syllabus", is_generalized_course=False))
        self.assertTrue(should_publish_material("Week 1 slides", "slides", is_generalized_course=True))
        self.assertFalse(should_publish_material("Data Vis 2022 - Outline", "outline", is_generalized_course=True))
        self.assertTrue(should_descend_into_material_folder("Slides", is_generalized_course=True))
        self.assertTrue(should_descend_into_material_folder("DV @ TAU - Lectures Archive", is_generalized_course=True))
        self.assertFalse(should_descend_into_material_folder("Exercises", is_generalized_course=True))
        self.assertFalse(should_descend_into_material_folder("Admin", is_generalized_course=True))
        self.assertFalse(should_descend_into_material_folder("Slides from Inbal", is_generalized_course=False))
        self.assertFalse(should_descend_into_material_folder("Course Polls", is_generalized_course=False))
        self.assertTrue(should_descend_into_material_folder("Slides", is_generalized_course=False))
        self.assertTrue(should_descend_into_material_folder("Exercises", is_generalized_course=False))

    def test_normalize_material_title_and_exclusion_reason(self) -> None:
        self.assertEqual(normalize_material_title(" Copy of  Week 1 slides "), "Week 1 slides")
        self.assertEqual(
            classify_material_exclusion("Copy of slides.pptx", "slides", is_generalized_course=False),
            "low-signal",
        )
        self.assertEqual(
            classify_material_exclusion("Grades Timeline", "sheet", is_generalized_course=False),
            "privacy-admin",
        )
        self.assertEqual(
            classify_material_exclusion("Course Timeline", "slides", is_generalized_course=False),
            "low-signal",
        )
        self.assertEqual(
            classify_material_exclusion("Home Exercise 2", "exercise", is_generalized_course=False),
            "disallowed-kind",
        )
        self.assertEqual(
            classify_material_exclusion("Lecture Deck", "slides", is_generalized_course=False),
            "low-signal",
        )
        self.assertEqual(
            classify_material_exclusion(
                "Deep Learning 24/5 - S4: Sequences, RNNs & Transformers",
                "slides",
                is_generalized_course=False,
            ),
            None,
        )
        self.assertIsNone(
            classify_material_exclusion(
                "Home Exercise 2",
                "exercise",
                is_generalized_course=False,
                publish_override=True,
            )
        )
        self.assertEqual(
            classify_material_exclusion(
                "Student Grades",
                "slides",
                is_generalized_course=False,
                publish_override=True,
            ),
            "privacy-admin",
        )

    def test_infer_week_section_sort_and_material_from_drive_item(self) -> None:
        self.assertEqual(infer_week("Week 3 - Task Abstraction"), 3)
        self.assertEqual(infer_week("TA Session #2 Exercise Notebook"), 2)
        self.assertEqual(infer_week("No date here"), None)
        self.assertEqual(infer_section("Week 1 slides", "slides"), "Weekly Materials")
        self.assertEqual(infer_section("Session 1 notebook", "notebook"), "Sessions")
        self.assertEqual(infer_section("Course syllabus", "syllabus"), "Course Outline")
        self.assertEqual(infer_section("Course outline", "outline"), "Course Outline")
        self.assertEqual(infer_section("Lecture deck", "slides"), "Course Materials")
        self.assertEqual(infer_section("Reference link", "resource"), "Additional Materials")
        self.assertEqual(infer_sort_key("Lecture 1", None), "99-lecture-1")

        material = material_from_drive_item(
            {
                "id": "file-1",
                "name": "Copy of Week 4 - Notebook",
                "mimeType": "application/vnd.google-apps.document",
                "webViewLink": "https://docs.google.com/document/d/example/edit",
            }
        )
        self.assertEqual(material.source_file_id, "file-1")
        self.assertEqual(material.title, "Week 4 - Notebook")
        self.assertEqual(material.kind, "notebook")
        self.assertEqual(material.week, 4)
        self.assertTrue(material.published)
        self.assertEqual(material.description, "Week 4 lecture notebook")

    def test_apply_concrete_course_content_uses_template_for_generic_or_empty_summary(self) -> None:
        generic = Course(
            slug="data-vis-25a",
            title="Data Vis",
            subtitle="Course page for teaching materials, 25/26 (Semester A)",
            institution="Unknown institution",
            role="Instructor",
            academic_period="25/26",
            status="active",
            source_drive_folder_id="folder-a",
            source_drive_folder_name="Data Vis 25/26A CF",
            summary="Teaching materials extracted from Google Drive folder 'Data Vis 25/26A CF'.",
            visibility="public",
            course_family="data-vis",
            section="A",
        )
        enriched = apply_concrete_course_content(generic)
        self.assertIn("This semester of Data Visualization focused on visual reasoning", enriched.summary)

        empty_summary = Course(
            slug="econml-24",
            title="Intro to ML @ MTA",
            subtitle="Course page for teaching materials, 24/25 (Semester A)",
            institution="The Academic College of Tel Aviv-Yaffo",
            role="Instructor",
            academic_period="24/25",
            status="active",
            source_drive_folder_id="folder-b",
            source_drive_folder_name="EconML 24/25A CF",
            summary="",
            visibility="public",
            course_family="econml",
            section="A",
        )
        enriched_empty = apply_concrete_course_content(empty_summary)
        self.assertIn("This semester of Intro to ML @ MTA focused on applied machine-learning thinking", enriched_empty.summary)

    def test_material_from_drive_item_falls_back_to_content_link(self) -> None:
        material = material_from_drive_item(
            {
                "id": "file-2",
                "name": "Reference",
                "mimeType": "text/plain",
                "webContentLink": "https://example.com/content.txt",
            }
        )
        self.assertEqual(material.url, "https://example.com/content.txt")
        self.assertEqual(material.kind, "resource")
        self.assertFalse(material.published)
