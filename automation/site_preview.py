from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from automation.config import Paths


PREVIEW_EXCLUDES = {
    ".git",
    ".automation-preview",
    "_site",
    ".bundle",
    ".envrc",
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
}


def prepare_preview_site(paths: Paths) -> tuple[Path, Path]:
    if not paths.preview_teaching_index.exists():
        raise FileNotFoundError(
            "No preview content found. Run `python3 -m automation.cli courses backfill --dry-run ...` first."
        )
    if paths.preview_site_source_root.exists():
        shutil.rmtree(paths.preview_site_source_root)
    if paths.preview_site_build_root.exists():
        shutil.rmtree(paths.preview_site_build_root)

    shutil.copytree(
        paths.repo_root,
        paths.preview_site_source_root,
        ignore=shutil.ignore_patterns(*PREVIEW_EXCLUDES),
    )
    preview_teaching_root = paths.preview_site_source_root / "teaching"
    preview_teaching_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(paths.preview_teaching_index, paths.preview_site_source_root / "teaching.md")
    for preview_page in paths.preview_teaching_root.glob("*.md"):
        shutil.copy2(preview_page, preview_teaching_root / preview_page.name)
    return paths.preview_site_source_root, paths.preview_site_build_root


def build_preview_site(paths: Paths, bundle_command: str = "bundle") -> tuple[Path, Path]:
    source_root, build_root = prepare_preview_site(paths)
    env = dict(os.environ)
    subprocess.run(
        [
            bundle_command,
            "exec",
            "jekyll",
            "build",
            "--source",
            str(source_root),
            "--destination",
            str(build_root),
        ],
        check=True,
        cwd=paths.repo_root,
        env=env,
    )
    return source_root, build_root


def serve_preview_site(
    paths: Paths,
    host: str = "127.0.0.1",
    port: int = 4001,
    bundle_command: str = "bundle",
) -> tuple[Path, Path]:
    source_root, build_root = prepare_preview_site(paths)
    env = dict(os.environ)
    subprocess.run(
        [
            bundle_command,
            "exec",
            "jekyll",
            "serve",
            "--source",
            str(source_root),
            "--destination",
            str(build_root),
            "--host",
            host,
            "--port",
            str(port),
        ],
        check=True,
        cwd=paths.repo_root,
        env=env,
    )
    return source_root, build_root
