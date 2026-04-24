from __future__ import annotations

import csv
import io
import re
from html import escape

from automation.models import Material


GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"


def select_syllabus_material(materials: list[Material]) -> Material | None:
    candidates = [item for item in materials if item.kind in {"syllabus", "outline"}]
    if not candidates:
        return None
    priority = {
        GOOGLE_DOC_MIME: 0,
        GOOGLE_SHEET_MIME: 1,
    }
    return sorted(
        candidates,
        key=lambda item: (
            priority.get(item.source_mime_type, 9),
            item.week is not None,
            item.sort_key.lower(),
            item.title.lower(),
        ),
    )[0]


def syllabus_export_mime(material: Material) -> str | None:
    if material.source_mime_type == GOOGLE_DOC_MIME:
        return "text/plain"
    if material.source_mime_type == GOOGLE_SHEET_MIME:
        return "text/tab-separated-values"
    return None


def render_syllabus_markdown(material: Material, exported_text: str) -> str:
    if material.source_mime_type == GOOGLE_DOC_MIME:
        return _doc_text_to_markdown(exported_text)
    if material.source_mime_type == GOOGLE_SHEET_MIME:
        return _tsv_to_markdown(exported_text)
    return ""


def _doc_text_to_markdown(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u2022", "*").replace("\uf0b7", "*")
    lines = [line.rstrip() for line in normalized.splitlines()]
    rendered: list[str] = []
    previous_blank = True
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
        if bullet:
            rendered.append(f"* {bullet.group(1).strip()}")
        else:
            rendered.append(line)
        previous_blank = False
    return "\n".join(rendered).strip()


def _tsv_to_markdown(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""
    rows = list(csv.reader(io.StringIO(normalized), delimiter="\t"))
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
    lines.extend(
        [
            "    </tr>",
            "  </thead>",
            "  <tbody>",
        ]
    )
    for row in body_rows:
        lines.append("    <tr>")
        for cell in row:
            lines.append(f"      <td>{cell}</td>")
        lines.append("    </tr>")
    lines.extend(
        [
            "  </tbody>",
            "</table>",
        ]
    )
    return "\n".join(lines).strip()
