from __future__ import annotations

import json
import os
from typing import Any

import requests

from automation.models import Course, Material


def rewrite_syllabus_markdown(course: Course, material: Material, exported_text: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("OPENAI_SYLLABUS_MODEL", "gpt-5.2").strip() or "gpt-5.2"
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    schema = {
        "name": "syllabus_outline",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "paragraph": {"type": "string"},
                "lectures": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "slot": {"type": "string"},
                            "title": {"type": "string"},
                            "focus": {"type": "string"},
                        },
                        "required": ["slot", "title", "focus"],
                    },
                    "maxItems": 8,
                },
            },
            "required": ["paragraph", "lectures"],
        },
        "strict": True,
    }
    prompt = (
        "You are rewriting a course syllabus export into compact website markdown content.\n"
        "Return a JSON object with:\n"
        "- paragraph: one concise paragraph under 90 words\n"
        "- lectures: up to 8 rows, one per lecture block, each with slot, title, and focus\n"
        "Use plain English. Exclude administrative items, grading policy, bibliography, surveys, and announcements.\n"
        f"Course title: {course.title}\n"
        f"Course subtitle: {course.subtitle}\n"
        f"Source material title: {material.title}\n\n"
        f"Syllabus source text:\n{exported_text[:12000]}"
    )
    response = requests.post(
        f"{base_url}/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema["name"],
                    "schema": schema["schema"],
                    "strict": True,
                }
            },
        },
        timeout=60,
    )
    if response.status_code != 200:
        return None
    payload = response.json()
    output_text = _response_output_text(payload)
    if not output_text:
        return None
    try:
        structured = json.loads(output_text)
    except json.JSONDecodeError:
        return None
    paragraph = str(structured.get("paragraph", "") or "").strip()
    lectures = list(structured.get("lectures", []) or [])
    if not paragraph and not lectures:
        return None
    return _render_compact_markdown(paragraph, lectures)


def _response_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return ""


def _render_compact_markdown(paragraph: str, lectures: list[dict[str, Any]]) -> str:
    lines = [paragraph.strip(), ""]
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
        for lecture in lectures:
            slot = str(lecture.get("slot", "") or "").strip()
            title = str(lecture.get("title", "") or "").strip()
            focus = str(lecture.get("focus", "") or "").strip()
            if not (slot or title or focus):
                continue
            lines.extend(
                [
                    "    <tr>",
                    f"      <td>{slot}</td>",
                    f"      <td>{title}</td>",
                    f"      <td>{focus}</td>",
                    "    </tr>",
                ]
            )
        lines.extend(["  </tbody>", "</table>"])
    return "\n".join(lines).strip()
