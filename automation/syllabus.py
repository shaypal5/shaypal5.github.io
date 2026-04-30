from __future__ import annotations

import csv
import io
import re
from html import escape

from automation.course_family_content import compact_concrete_syllabus_content
from automation.models import Course, Material
from automation.openai_syllabus import rewrite_syllabus_markdown


GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_INLINE_SYLLABUS_WORDS = 250

ADMIN_TEXT_TERMS = (
    "course repository",
    "moodle",
    "mama",
    "annoucements",
    "announcements",
    "לוח הודעות",
    "google calendar events for all lectures",
    "validate no holidays",
)

LOW_SIGNAL_TEXT_TERMS = (
    "לינקים לדברים",
    "lecture quality survey",
    "שאלון סטטוס",
)


def sorted_syllabus_materials(materials: list[Material]) -> list[Material]:
    candidates = [item for item in materials if item.published and item.kind in {"syllabus", "outline"}]
    if not candidates:
        return []
    priority = {
        GOOGLE_DOC_MIME: 0,
        DOCX_MIME: 1,
        GOOGLE_SHEET_MIME: 2,
    }
    return sorted(
        candidates,
        key=lambda item: (
            priority.get(item.source_mime_type, 9),
            item.kind != "syllabus",
            item.week is not None,
            item.sort_key.lower(),
            item.title.lower(),
        ),
    )


def select_syllabus_material(materials: list[Material]) -> Material | None:
    candidates = sorted_syllabus_materials(materials)
    if not candidates:
        return None
    return candidates[0]


def syllabus_export_mime(material: Material) -> str | None:
    if material.source_mime_type == GOOGLE_DOC_MIME:
        return "text/plain"
    if material.source_mime_type == GOOGLE_SHEET_MIME:
        return "text/tab-separated-values"
    return None


def render_syllabus_markdown(material: Material, exported_text: str, course: Course | None = None) -> str:
    normalized_text = _normalize_text(exported_text)
    if not normalized_text:
        return ""

    if _looks_like_admin_dump(material, normalized_text):
        return ""

    if course and not course.is_generalized:
        llm_markdown = _maybe_rewrite_with_openai(course, material, normalized_text)
        if llm_markdown:
            return llm_markdown
        compact_markdown = _compact_family_markdown(course)
        if compact_markdown and _should_use_compact_family_outline(course, material, normalized_text):
            return compact_markdown

    if material.source_mime_type in {GOOGLE_DOC_MIME, DOCX_MIME}:
        return _doc_text_to_markdown(normalized_text)
    if material.source_mime_type == GOOGLE_SHEET_MIME:
        if _sheet_needs_compaction(normalized_text):
            return ""
        return _tsv_to_markdown(normalized_text)
    return ""


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _looks_like_admin_dump(material: Material, text: str) -> bool:
    lowered = f"{material.title}\n{text[:4000]}".casefold()
    if any(term in lowered for term in ADMIN_TEXT_TERMS):
        return True
    if material.kind == "outline" and any(term in lowered for term in LOW_SIGNAL_TEXT_TERMS):
        return True
    return False


def _should_use_compact_family_outline(course: Course, material: Material, text: str) -> bool:
    if course.course_family in {"data-vis", "deep-learning"}:
        return True
    if material.source_mime_type == GOOGLE_SHEET_MIME and _sheet_needs_compaction(text):
        return True
    return False


def _sheet_needs_compaction(text: str) -> bool:
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    rows = [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return False
    header = [cell.casefold() for cell in rows[0]]
    if any("done?" in cell for cell in header):
        return True
    if any("week \\ axis" in cell for cell in header):
        return True
    return len(header) > 6


def _maybe_rewrite_with_openai(course: Course, material: Material, text: str) -> str | None:
    if material.source_mime_type not in {GOOGLE_DOC_MIME, DOCX_MIME, GOOGLE_SHEET_MIME}:
        return None
    return rewrite_syllabus_markdown(course, material, text)


def _compact_family_markdown(course: Course) -> str:
    content = compact_concrete_syllabus_content(course.course_family)
    if content is None:
        return ""
    paragraph = str(content.get("paragraph", "") or "").strip()
    lectures = list(content.get("lectures", []) or [])
    lines = [paragraph, ""]
    if lectures:
        lines.extend(
            [
                '<table class="course-outline-table compact-course-outline-table">',
                "  <thead>",
                "    <tr>",
                "      <th>Lecture</th>",
                "      <th>Topic</th>",
                "      <th>Focus</th>",
                "    </tr>",
                "  </thead>",
                "  <tbody>",
            ]
        )
        for slot, title, focus in lectures:
            lines.extend(
                [
                    "    <tr>",
                    f"      <td>{escape(str(slot))}</td>",
                    f"      <td>{escape(str(title))}</td>",
                    f"      <td>{escape(str(focus))}</td>",
                    "    </tr>",
                ]
            )
        lines.extend(["  </tbody>", "</table>"])
    return "\n".join(lines).strip()


def default_compact_syllabus_markdown(course: Course) -> str:
    return _compact_family_markdown(course)


def _doc_text_to_markdown(text: str) -> str:
    normalized = text.replace("\u2022", "*").replace("\uf0b7", "*")
    lines = [line.rstrip() for line in normalized.splitlines()]
    rendered: list[str] = []
    previous_blank = True
    word_budget = MAX_INLINE_SYLLABUS_WORDS
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if not previous_blank and rendered:
                rendered.append("")
            previous_blank = True
            continue
        if re.fullmatch(r"https?://\S+", line):
            continue
        bullet = re.match(r"^(?:[*\-•]\s+|\d+[.)]\s+)(.+)$", line)
        candidate = f"* {bullet.group(1).strip()}" if bullet else line
        words = candidate.split()
        if len(words) > word_budget:
            candidate = " ".join(words[:word_budget]).rstrip() + "..."
            rendered.append(candidate)
            break
        rendered.append(candidate)
        word_budget -= len(words)
        previous_blank = False
        if word_budget <= 0:
            break
    return "\n".join(rendered).strip()


def _tsv_to_markdown(text: str) -> str:
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    rows = [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header = padded[0]
    body_rows: list[list[str]] = []
    for row in padded[1:]:
        if body_rows and not row[0]:
            merged = body_rows[-1]
            for index, cell in enumerate(row):
                if not cell:
                    continue
                merged[index] = f"{merged[index]}<br>{escape(cell)}" if merged[index] else escape(cell)
            continue
        body_rows.append([escape(cell) for cell in row])

    lines = [
        '<table class="course-outline-table">',
        "  <thead>",
        "    <tr>",
    ]
    for cell in header:
        lines.append(f"      <th>{escape(cell)}</th>")
    lines.extend(["    </tr>", "  </thead>", "  <tbody>"])
    for row in body_rows:
        lines.append("    <tr>")
        for cell in row:
            lines.append(f"      <td>{cell}</td>")
        lines.append("    </tr>")
    lines.extend(["  </tbody>", "</table>"])
    return "\n".join(lines).strip()
