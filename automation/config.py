from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"
GENERATED_HEADER = "<!-- GENERATED: edit data/teaching or automation sources instead of this file. -->"
TEACHING_MARKER_START = "<!-- BEGIN GENERATED: teaching-courses -->"
TEACHING_MARKER_END = "<!-- END GENERATED: teaching-courses -->"


class AutomationError(Exception):
    """Base automation error."""


class ValidationError(AutomationError):
    """Raised when repository validation fails."""


class AuthConfigError(AutomationError):
    """Raised when auth or local config is missing."""


class DiscoveryError(AutomationError):
    """Raised when upstream discovery fails."""


class PublishError(AutomationError):
    """Raised when publish or PR creation fails."""


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    data_root: Path
    materials_root: Path
    teaching_root: Path
    teaching_index: Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_paths(root: Path | None = None) -> Paths:
    resolved = root or repo_root()
    return Paths(
        repo_root=resolved,
        data_root=resolved / "data" / "teaching",
        materials_root=resolved / "data" / "teaching" / "materials",
        teaching_root=resolved / "teaching",
        teaching_index=resolved / "teaching.md",
    )


def required_google_env() -> dict[str, str]:
    env = {
        "GOOGLE_OAUTH_CLIENT_ID": os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
        "GOOGLE_OAUTH_CLIENT_SECRET": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
        "GOOGLE_OAUTH_REFRESH_TOKEN": os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "").strip(),
        "GOOGLE_OAUTH_TOKEN_URI": os.getenv("GOOGLE_OAUTH_TOKEN_URI", TOKEN_URI_DEFAULT).strip()
        or TOKEN_URI_DEFAULT,
    }
    missing = [name for name, value in env.items() if name != "GOOGLE_OAUTH_TOKEN_URI" and not value]
    if missing:
        raise AuthConfigError(
            "Missing required Google OAuth environment variables: " + ", ".join(sorted(missing))
        )
    return env


def drive_roots() -> list[str]:
    raw = os.getenv("GOOGLE_DRIVE_ROOTS", "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
