from __future__ import annotations

from dataclasses import dataclass, field


REQUIRED_COURSE_FIELDS = [
    "slug",
    "title",
    "subtitle",
    "institution",
    "role",
    "academic_period",
    "status",
    "source_drive_folder_id",
    "source_drive_folder_name",
    "summary",
    "visibility",
]

REQUIRED_MATERIAL_FIELDS = [
    "title",
    "url",
    "kind",
    "week",
    "section",
    "source_file_id",
    "source_mime_type",
    "published",
    "sort_key",
    "notes",
]


@dataclass
class Material:
    title: str
    url: str
    kind: str
    week: int | None = None
    section: str = ""
    source_file_id: str = ""
    source_mime_type: str = ""
    published: bool = True
    sort_key: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "Material":
        return cls(
            title=payload.get("title", ""),
            url=payload.get("url", ""),
            kind=payload.get("kind", ""),
            week=payload.get("week"),
            section=payload.get("section", "") or "",
            source_file_id=payload.get("source_file_id", "") or "",
            source_mime_type=payload.get("source_mime_type", "") or "",
            published=bool(payload.get("published", False)),
            sort_key=str(payload.get("sort_key", "") or ""),
            notes=payload.get("notes", "") or "",
        )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "kind": self.kind,
            "week": self.week,
            "section": self.section,
            "source_file_id": self.source_file_id,
            "source_mime_type": self.source_mime_type,
            "published": self.published,
            "sort_key": self.sort_key,
            "notes": self.notes,
        }


@dataclass
class Course:
    slug: str
    title: str
    subtitle: str
    institution: str
    role: str
    academic_period: str
    status: str
    source_drive_folder_id: str
    source_drive_folder_name: str
    summary: str
    visibility: str
    syllabus_url: str = ""
    hero_note: str = ""
    tags: list[str] = field(default_factory=list)
    manual_overrides: dict = field(default_factory=dict)
    review_notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "Course":
        return cls(
            slug=payload.get("slug", ""),
            title=payload.get("title", ""),
            subtitle=payload.get("subtitle", ""),
            institution=payload.get("institution", ""),
            role=payload.get("role", ""),
            academic_period=payload.get("academic_period", ""),
            status=payload.get("status", ""),
            source_drive_folder_id=payload.get("source_drive_folder_id", ""),
            source_drive_folder_name=payload.get("source_drive_folder_name", ""),
            summary=payload.get("summary", ""),
            visibility=payload.get("visibility", ""),
            syllabus_url=payload.get("syllabus_url", "") or "",
            hero_note=payload.get("hero_note", "") or "",
            tags=list(payload.get("tags", []) or []),
            manual_overrides=dict(payload.get("manual_overrides", {}) or {}),
            review_notes=payload.get("review_notes", "") or "",
        )

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "subtitle": self.subtitle,
            "institution": self.institution,
            "role": self.role,
            "academic_period": self.academic_period,
            "status": self.status,
            "source_drive_folder_id": self.source_drive_folder_id,
            "source_drive_folder_name": self.source_drive_folder_name,
            "summary": self.summary,
            "visibility": self.visibility,
            "syllabus_url": self.syllabus_url,
            "hero_note": self.hero_note,
            "tags": self.tags,
            "manual_overrides": self.manual_overrides,
            "review_notes": self.review_notes,
        }
