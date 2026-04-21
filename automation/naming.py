from __future__ import annotations

import re
import unicodedata

from automation.models import Course, Material


COURSE_SUFFIX = " CF"

INSTITUTION_HINTS = {
    "TAU": "Tel Aviv University",
    "MTA": "The Academic College of Tel Aviv-Yaffo",
    "DATANIGHTS": "DataNights",
}


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return cleaned or "course"


def parse_course_folder_name(folder_name: str) -> dict[str, str]:
    base = folder_name.removesuffix(COURSE_SUFFIX).strip()
    no_year = re.sub(r"\b(20\d{2}|[0-9]{2}'-[0-9]{2}'|[0-9]{2}')\b", "", base).strip(" -_,")
    title_part = no_year
    role = "Instructor"
    if " TA " in f" {base} " or base.upper().startswith("TA "):
        role = "Teaching Assistant"
    institution = ""
    for hint, expanded in INSTITUTION_HINTS.items():
        if hint.lower() in base.lower():
            institution = expanded
            break
    period_match = re.search(r"(20\d{2}|[0-9]{2}'-[0-9]{2}'|[0-9]{2}'?|[0-9]{2})", base)
    academic_period = period_match.group(1) if period_match else "TBD"
    title_part = re.sub(r"\s*@\s*[A-Za-z0-9'. -]+", "", title_part).strip()
    title_part = re.sub(r"\b(?:TAU|MTA|DataNights)\b", "", title_part, flags=re.IGNORECASE).strip(" -_,")
    title_part = re.sub(r"\b(?:TA)\b", "", title_part, flags=re.IGNORECASE).strip(" -_,")
    title = title_part or no_year or base
    slug = slugify(title + "-" + academic_period.replace("'", ""))
    subtitle = f"Course page for {institution or 'teaching materials'}, {academic_period}"
    return {
        "slug": slug,
        "title": title,
        "subtitle": subtitle,
        "institution": institution or "Unknown institution",
        "role": role,
        "academic_period": academic_period,
    }


def infer_course_from_folder(folder_id: str, folder_name: str) -> Course:
    parsed = parse_course_folder_name(folder_name)
    summary = f"Teaching materials extracted from Google Drive folder '{folder_name}'."
    return Course(
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
    )


def classify_material_kind(name: str, mime_type: str) -> str:
    lowered = f"{name} {mime_type}".lower()
    if "syllabus" in lowered:
        return "syllabus"
    if "slide" in lowered or "presentation" in lowered:
        return "slides"
    if "notebook" in lowered or "colab" in lowered or "ipynb" in lowered:
        return "notebook"
    if "exercise" in lowered:
        return "exercise"
    if "solution" in lowered:
        return "solution"
    if "form" in lowered or "poll" in lowered:
        return "form"
    if "sheet" in lowered or mime_type.endswith("spreadsheet"):
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
    if kind == "syllabus":
        return "Course Outline"
    if kind in {"slides", "notebook", "exercise", "solution", "form"}:
        return "Course Materials"
    return "Additional Materials"


def infer_sort_key(name: str, week: int | None) -> str:
    lowered = name.lower()
    prefix = f"{week:02d}" if week is not None else "99"
    return f"{prefix}-{slugify(lowered)}"


def material_from_drive_item(item: dict) -> Material:
    name = item.get("name", "")
    mime_type = item.get("mimeType", "")
    kind = classify_material_kind(name, mime_type)
    week = infer_week(name)
    url = item.get("webViewLink") or item.get("webContentLink") or ""
    return Material(
        title=name,
        url=url,
        kind=kind,
        week=week,
        section=infer_section(name, kind),
        source_file_id=item.get("id", ""),
        source_mime_type=mime_type,
        published=bool(url),
        sort_key=infer_sort_key(name, week),
        notes="",
    )
