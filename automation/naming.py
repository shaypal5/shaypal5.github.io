from __future__ import annotations

import re
import unicodedata

from automation.course_family_content import apply_generalized_course_content
from automation.models import Course, Material


COURSE_SUFFIX = " CF"
ACADEMIC_RANGE_PATTERN = re.compile(
    r"(?P<start>(?:20)?\d{2})\s*[/\-]\s*(?P<end>(?:20)?\d{1,2})(?P<section>[A-Za-z])?$"
)
SINGLE_YEAR_PATTERN = re.compile(r"(20\d{2}|[0-9]{2}'-[0-9]{2}'|[0-9]{2}'?|[0-9]{2})")
GENERALIZED_SUFFIX_PATTERN = re.compile(r"\s*-\s*generalized$", re.IGNORECASE)
MATERIAL_FOLDER_TERMS = (
    "slide",
    "slides",
    "presentation",
    "presentations",
    "lecture",
    "lectures",
    "material",
    "materials",
    "notebook",
    "notebooks",
    "exercise",
    "exercises",
    "solution",
    "solutions",
    "archive",
)

BLACKLISTED_NAME_TERMS = (
    "grade",
    "grades",
    "submission",
    "submissions",
    "student",
    "students",
    "feedback",
    "attendance",
    "roster",
    "calendar",
    "quiz",
    "exam",
    "midterm",
    "final",
    "homework",
    "assignment",
    "from inbal",
    "survey",
    "poll",
    "form",
    "סקר",
    "טופס",
    "שאלון",
    "לוח שנה",
    "ציונים",
    "הגשות",
    "סטודנט",
    "נוכחות",
)

INSTITUTION_HINTS = {
    "TAU": "Tel Aviv University",
    "MTA": "The Academic College of Tel Aviv-Yaffo",
    "DATANIGHTS": "DataNights",
}


def is_valid_course_folder_name(folder_name: str) -> bool:
    if not folder_name.endswith(COURSE_SUFFIX):
        return False
    base = folder_name.removesuffix(COURSE_SUFFIX)
    return bool(base.strip())


def _normalize_year_token(token: str) -> str:
    digits = token.strip().replace("'", "")
    if len(digits) == 4:
        return digits[-2:]
    return digits


def _normalize_academic_range(start: str, end: str) -> str:
    start_token = _normalize_year_token(start)
    end_token = _normalize_year_token(end)
    if len(end_token) < len(start_token):
        end_token = start_token[: len(start_token) - len(end_token)] + end_token
    return f"{start_token}/{end_token}"


def _build_course_slug(title: str, academic_period: str, section: str) -> str:
    base_slug = slugify(title)
    if academic_period == "TBD":
        return base_slug
    range_match = re.fullmatch(r"(\d{2})/(\d{2})", academic_period)
    period_token = range_match.group(1) if range_match else academic_period.replace("/", "-").replace("'", "")
    section_token = section.lower()
    return slugify(f"{title}-{period_token}{section_token}")


def _material_description(kind: str, week: int | None) -> str:
    label = {
        "slides": "Lecture slides",
        "notebook": "Lecture notebook",
        "outline": "Course outline",
        "syllabus": "Course syllabus",
    }.get(kind, "Course material")
    if week is not None and kind in {"slides", "notebook"}:
        return f"Week {week} {label.lower()}"
    return label


def should_publish_material(name: str, kind: str, is_generalized_course: bool) -> bool:
    lowered = name.casefold()
    if any(term in lowered for term in BLACKLISTED_NAME_TERMS):
        return False
    allowed_kinds = (
        {"slides", "notebook"}
        if is_generalized_course
        else {"slides", "notebook", "outline", "syllabus", "exercise", "solution", "form"}
    )
    return kind in allowed_kinds


def should_descend_into_material_folder(name: str, is_generalized_course: bool) -> bool:
    lowered = name.casefold()
    if any(term in lowered for term in BLACKLISTED_NAME_TERMS):
        return False
    if is_generalized_course:
        return any(term in lowered for term in MATERIAL_FOLDER_TERMS if term not in {"exercise", "exercises", "solution", "solutions"})
    return any(term in lowered for term in MATERIAL_FOLDER_TERMS)


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return cleaned or "course"


def parse_course_folder_name(folder_name: str) -> dict[str, str]:
    base = folder_name.removesuffix(COURSE_SUFFIX).strip()
    is_generalized = bool(GENERALIZED_SUFFIX_PATTERN.search(base))
    family_base = GENERALIZED_SUFFIX_PATTERN.sub("", base).strip(" -_,")
    period_match = ACADEMIC_RANGE_PATTERN.search(base)
    section = ""
    if period_match:
        academic_period = _normalize_academic_range(period_match.group("start"), period_match.group("end"))
        section = (period_match.group("section") or "").upper()
        title_part = family_base[: period_match.start()].strip(" -_,")
    else:
        single_year_match = SINGLE_YEAR_PATTERN.search(family_base)
        academic_period = _normalize_year_token(single_year_match.group(1)) if single_year_match else "TBD"
        title_part = SINGLE_YEAR_PATTERN.sub("", family_base).strip(" -_,")
    no_year = title_part
    role = "Instructor"
    if " TA " in f" {base} " or base.upper().startswith("TA "):
        role = "Teaching Assistant"
    institution = ""
    for hint, expanded in INSTITUTION_HINTS.items():
        if hint.lower() in base.lower():
            institution = expanded
            break
    title_part = re.sub(r"\s*@\s*[A-Za-z0-9'. -]+", "", title_part).strip()
    title_part = re.sub(r"\b(?:TAU|MTA|DataNights)\b", "", title_part, flags=re.IGNORECASE).strip(" -_,")
    title_part = re.sub(r"\b(?:TA)\b", "", title_part, flags=re.IGNORECASE).strip(" -_,")
    title = title_part or no_year or base
    course_family = slugify(title)
    slug = course_family if is_generalized else _build_course_slug(title, academic_period, section)
    subtitle = f"Course page for {institution or 'teaching materials'}"
    if academic_period != "TBD":
        subtitle += f", {academic_period}"
    if section:
        subtitle += f" (Section {section})"
    if is_generalized:
        subtitle += " (Shared materials across course iterations)"
    return {
        "slug": slug,
        "title": title,
        "subtitle": subtitle,
        "institution": institution or "Unknown institution",
        "role": role,
        "academic_period": academic_period,
        "course_family": course_family,
        "section": section,
        "is_generalized": is_generalized,
    }


def infer_course_from_folder(folder_id: str, folder_name: str) -> Course:
    parsed = parse_course_folder_name(folder_name)
    summary = f"Teaching materials extracted from Google Drive folder '{folder_name}'."
    manual_overrides = {}
    if parsed["course_family"] == "data-vis":
        manual_overrides["section_label"] = "Semester"
        if parsed["section"]:
            parsed["subtitle"] = parsed["subtitle"].replace(
                f"(Section {parsed['section']})",
                f"(Semester {parsed['section']})",
            )
    course = Course(
        slug=parsed["slug"],
        title=parsed["title"],
        subtitle=parsed["subtitle"],
        institution=parsed["institution"],
        role=parsed["role"],
        academic_period=parsed["academic_period"],
        status="active",
        source_drive_folder_id=folder_id,
        source_drive_folder_name=folder_name,
        summary=summary,
        visibility="public",
        manual_overrides=manual_overrides,
        course_family=parsed["course_family"],
        section=parsed["section"],
        is_generalized=bool(parsed["is_generalized"]),
    )
    return apply_generalized_course_content(course)


def classify_material_kind(name: str, mime_type: str) -> str:
    name_lower = name.lower()
    lowered = f"{name_lower} {mime_type.lower()}"
    if "syllabus" in name_lower or "סילבוס" in name_lower:
        return "syllabus"
    if "outline" in name_lower or "details" in name_lower or "פרטים" in name_lower:
        return "outline"
    if "slide" in name_lower or "presentation" in name_lower or mime_type.endswith("presentation"):
        return "slides"
    if "notebook" in name_lower or "colab" in name_lower or "ipynb" in name_lower:
        return "notebook"
    if "exercise" in name_lower:
        return "exercise"
    if "solution" in name_lower:
        return "solution"
    if "form" in name_lower or "poll" in name_lower or "survey" in name_lower or "סקר" in name_lower or "טופס" in name_lower or "שאלון" in name_lower:
        return "form"
    if "sheet" in name_lower or mime_type.endswith("spreadsheet"):
        return "sheet"
    return "resource"


def infer_week(name: str) -> int | None:
    patterns = [
        r"\bweek\s*(\d+)\b",
        r"\bw(\d+)\b",
        r"\bsession\s*#?\s*(\d+)\b",
        r"\blecture\s*(\d+)\b",
        r"\bs(\d+)\b",
    ]
    lowered = name.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))
    return None


def infer_section(name: str, kind: str) -> str:
    lowered = name.lower()
    if "week" in lowered:
        return "Weekly Materials"
    if "session" in lowered:
        return "Sessions"
    if kind in {"syllabus", "outline"}:
        return "Course Outline"
    if kind in {"slides", "notebook", "exercise", "solution", "form"}:
        return "Course Materials"
    return "Additional Materials"


def infer_sort_key(name: str, week: int | None) -> str:
    lowered = name.lower()
    prefix = f"{week:02d}" if week is not None else "99"
    return f"{prefix}-{slugify(lowered)}"


def material_from_drive_item(item: dict, is_generalized_course: bool = False) -> Material:
    name = item.get("name", "")
    mime_type = item.get("mimeType", "")
    kind = classify_material_kind(name, mime_type)
    week = infer_week(name)
    url = item.get("webViewLink") or item.get("webContentLink") or ""
    published = bool(url) and should_publish_material(name, kind, is_generalized_course)
    return Material(
        title=name,
        url=url,
        kind=kind,
        week=week,
        section=infer_section(name, kind),
        source_file_id=item.get("id", ""),
        source_mime_type=mime_type,
        published=published,
        sort_key=infer_sort_key(name, week),
        notes="",
        description=_material_description(kind, week),
    )
