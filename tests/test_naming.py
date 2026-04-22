import unittest

from automation.models import Course
from automation.naming import (
    classify_material_kind,
    infer_course_from_folder,
    infer_section,
    infer_sort_key,
    infer_week,
    is_valid_course_folder_name,
    material_from_drive_item,
    parse_course_folder_name,
    should_publish_material,
    slugify,
)


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
        self.assertIn("Section A", parsed["subtitle"])

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
        self.assertIn("Section B", parsed["subtitle"])

    def test_parse_course_folder_name_ta_and_unknown_institution(self) -> None:
        parsed = parse_course_folder_name("TA Deep Learning Bootcamp 2024 CF")
        self.assertEqual(parsed["role"], "Teaching Assistant")
        self.assertEqual(parsed["institution"], "Unknown institution")
        self.assertEqual(parsed["academic_period"], "24")

    def test_slugify_and_infer_course(self) -> None:
        self.assertEqual(slugify("Café & ML"), "cafe-ml")
        course = infer_course_from_folder("folder-1", "DataNights Leadership 24 CF")
        self.assertIsInstance(course, Course)
        self.assertEqual(course.source_drive_folder_id, "folder-1")
        self.assertEqual(course.visibility, "public")
        generalized = infer_course_from_folder("folder-2", "Data Vis - Generalized CF")
        self.assertTrue(generalized.is_generalized)
        self.assertEqual(generalized.course_family, "data-vis")

    def test_classify_material_kind(self) -> None:
        self.assertEqual(classify_material_kind("Course Syllabus", "application/pdf"), "syllabus")
        self.assertEqual(classify_material_kind("Data Vis 2022 - Outline", "application/vnd.google-apps.spreadsheet"), "outline")
        self.assertEqual(classify_material_kind("קורס ויזואליזציה - פרטים", "application/vnd.google-apps.document"), "outline")
        self.assertEqual(
            classify_material_kind("Week 2 - Lecture Slides", "application/vnd.google-apps.presentation"),
            "slides",
        )
        self.assertEqual(classify_material_kind("Notebook.ipynb", "text/plain"), "notebook")
        self.assertEqual(classify_material_kind("Exercise 1", "text/plain"), "exercise")
        self.assertEqual(classify_material_kind("Solution 1", "text/plain"), "solution")
        self.assertEqual(classify_material_kind("Poll Form", "text/plain"), "form")
        self.assertEqual(
            classify_material_kind("Results", "application/vnd.google-apps.spreadsheet"),
            "sheet",
        )
        self.assertEqual(classify_material_kind("Reference URL", "text/plain"), "resource")

    def test_valid_course_folder_name_and_publish_rules(self) -> None:
        self.assertTrue(is_valid_course_folder_name("Data Vis 22/23A CF"))
        self.assertFalse(is_valid_course_folder_name("Data Vis 22/23A Cf"))
        self.assertFalse(should_publish_material("Course Exercise 1", "exercise", is_generalized_course=False))
        self.assertFalse(should_publish_material("לוח שנה תשפד - לוח 3.pdf", "resource", is_generalized_course=False))
        self.assertTrue(should_publish_material("Week 1 slides", "slides", is_generalized_course=True))
        self.assertFalse(should_publish_material("Data Vis 2022 - Outline", "outline", is_generalized_course=True))

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
                "name": "Week 4 - Notebook",
                "mimeType": "application/vnd.google-apps.document",
                "webViewLink": "https://docs.google.com/document/d/example/edit",
            }
        )
        self.assertEqual(material.source_file_id, "file-1")
        self.assertEqual(material.kind, "notebook")
        self.assertEqual(material.week, 4)
        self.assertTrue(material.published)
        self.assertEqual(material.description, "Week 4 lecture notebook")

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
