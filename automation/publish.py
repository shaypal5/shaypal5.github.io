from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from automation.config import PublishError, repo_root


@dataclass
class PublishResult:
    branch: str
    pr_url: str


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PublishError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def ensure_branch(branch: str) -> None:
    current = run_git(["branch", "--show-current"])
    if current != branch:
        run_git(["checkout", "-B", branch])


def commit_all(message: str) -> None:
    run_git(["add", "automation", "data", "docs", "tests", ".github", "teaching", "teaching.md", "_config.yml", ".gitignore", "pyproject.toml"])
    if not run_git(["status", "--short"]):
        return
    run_git(["commit", "-m", message])


def push_branch(branch: str) -> None:
    run_git(["push", "-u", "origin", branch])


def create_pull_request(title: str, body: str, label: str = "teaching") -> str:
    repo = os.getenv("GITHUB_REPO", "shaypal5/shaypal5.github.io")
    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            body,
            "--label",
            label,
        ],
        cwd=repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PublishError(result.stderr.strip() or result.stdout.strip() or "gh pr create failed")
    stdout = result.stdout.strip()
    if not stdout:
        raise PublishError("gh pr create succeeded but produced no output")
    return stdout.splitlines()[-1]


def publish_changes(branch: str, title: str, body: str, commit_message: str) -> PublishResult:
    ensure_branch(branch)
    commit_all(commit_message)
    push_branch(branch)
    pr_url = create_pull_request(title=title, body=body)
    return PublishResult(branch=branch, pr_url=pr_url)
