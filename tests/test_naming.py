import unittest

from automation.naming import classify_material_kind, infer_week, parse_course_folder_name


class NamingTests(unittest.TestCase):
    def test_parse_course_folder_name(self) -> None:
        parsed = parse_course_folder_name("Intro to ML @ MTA 25 CF")
        self.assertEqual(parsed["institution"], "The Academic College of Tel Aviv-Yaffo")
        self.assertEqual(parsed["academic_period"], "25")
        self.assertTrue(parsed["slug"].startswith("intro-to-ml"))

    def test_classify_material_kind(self) -> None:
        self.assertEqual(classify_material_kind("Course Syllabus", "application/pdf"), "syllabus")
        self.assertEqual(
            classify_material_kind("Week 2 - Lecture Slides", "application/vnd.google-apps.presentation"),
            "slides",
        )

    def test_infer_week(self) -> None:
        self.assertEqual(infer_week("Week 3 - Task Abstraction"), 3)
        self.assertEqual(infer_week("TA Session #2 Exercise Notebook"), 2)


if __name__ == "__main__":
    unittest.main()
