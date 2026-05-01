from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import requests
import yaml

from automation.config import Paths


DEFAULT_ALLOWLIST_PATH = Path("automation/external_link_allowlist.yml")
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRIES = 1
DEFAULT_MAX_WORKERS = 8
DEFAULT_SOURCE = "rendered"
SOFT_SUCCESS_STATUSES = {401, 403, 429}
PUBLIC_ROOT_MARKDOWN_EXCLUDES = {"AGENTS.md", "README.md", "llms.txt", ".agent-plan.md"}
TRAILING_URL_CHARS = ".,;:"
LINK_ATTRS = {"href", "src"}
URL_META_PROPERTIES = {"og:url", "og:image", "og:image:secure_url"}
URL_META_NAMES = {"twitter:image", "twitter:image:src"}
JSON_LD_SCRIPT_TYPE = "application/ld+json"

MARKDOWN_URL_RE = re.compile(r"\]\((https?://[^)\s]+)")
RAW_URL_RE = re.compile(r"https?://[^\s<>'\"\])}]+")


@dataclass(frozen=True)
class LinkOccurrence:
    path: Path
    line: int


@dataclass
class ExternalLink:
    url: str
    occurrences: list[LinkOccurrence] = field(default_factory=list)


@dataclass(frozen=True)
class LinkCollectionFailure:
    path: Path
    line: int
    message: str


@dataclass
class LinkCollectionResult:
    links: dict[str, ExternalLink]
    failures: list[LinkCollectionFailure] = field(default_factory=list)


@dataclass(frozen=True)
class AllowlistRule:
    match: str
    value: str
    reason: str
    include_subdomains: bool = True

    def matches(self, url: str) -> bool:
        parsed = urlparse(url)
        if self.match == "domain":
            host = (parsed.hostname or "").lower()
            value = self.value.lower()
            return host == value or (self.include_subdomains and host.endswith(f".{value}"))
        if self.match == "prefix":
            return url.startswith(self.value)
        if self.match == "exact":
            return url == self.value
        if self.match == "regex":
            return re.search(self.value, url) is not None
        return False


@dataclass(frozen=True)
class LinkCheckConfig:
    allowlist_path: Path
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES
    max_workers: int = DEFAULT_MAX_WORKERS
    source: str = DEFAULT_SOURCE
    site_root: Path | None = None


@dataclass
class LinkCheckSummary:
    checked: int
    skipped: int
    failures: list[str]
    skipped_by_rule: dict[str, int]


class LinkHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[tuple[str, int]] = []
        self.json_ld_failures: list[tuple[int, str]] = []
        self._script_type: str | None = None
        self._script_line: int | None = None
        self._script_data: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, _ = self.getpos()
        attr_map = {name.lower(): value for name, value in attrs if value}
        for name, value in attrs:
            if name in LINK_ATTRS and value:
                self.urls.append((value, line))
        if tag == "meta":
            content = attr_map.get("content")
            property_name = attr_map.get("property", "").lower()
            meta_name = attr_map.get("name", "").lower()
            if content and (
                property_name in URL_META_PROPERTIES or meta_name in URL_META_NAMES
            ):
                self.urls.append((content, line))
        if tag == "script":
            script_type = attr_map.get("type", "").split(";", maxsplit=1)[0].strip().lower()
            self._script_type = script_type or None
            self._script_line = line
            self._script_data = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            if self._script_type == JSON_LD_SCRIPT_TYPE:
                self._extract_json_ld_urls("".join(self._script_data))
            self._script_type = None
            self._script_line = None
            self._script_data = []

    def handle_data(self, data: str) -> None:
        if self._script_type != JSON_LD_SCRIPT_TYPE:
            return
        self._script_data.append(data)

    def _extract_json_ld_urls(self, data: str) -> None:
        line = self._script_line or 1
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            self.json_ld_failures.append(
                (
                    line,
                    "malformed JSON-LD script could not be parsed: "
                    f"{exc.msg} at JSON line {exc.lineno} column {exc.colno}",
                )
            )
            return
        for url in _json_string_urls(payload):
            self.urls.append((url, line))


def _json_string_urls(value: object) -> set[str]:
    urls: set[str] = set()
    if isinstance(value, str):
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            urls.add(value)
    elif isinstance(value, list):
        for item in value:
            urls.update(_json_string_urls(item))
    elif isinstance(value, dict):
        for item in value.values():
            urls.update(_json_string_urls(item))
    return urls


def _source_content_paths(paths: Paths) -> list[Path]:
    root_markdown = [
        path
        for path in paths.repo_root.glob("*.md")
        if path.name not in PUBLIC_ROOT_MARKDOWN_EXCLUDES
    ]
    include_markdown = sorted((paths.repo_root / "_includes").glob("*.md"))
    teaching_markdown = sorted(paths.teaching_root.glob("*.md"))
    data_yaml = sorted(paths.site_data_root.glob("*.yml"))
    teaching_yaml = sorted(paths.data_root.glob("*.yml")) + sorted(paths.materials_root.glob("*.yml"))
    return sorted({*root_markdown, *include_markdown, *teaching_markdown, *data_yaml, *teaching_yaml})


def _rendered_content_paths(site_root: Path) -> list[Path]:
    if not site_root.exists():
        raise FileNotFoundError(f"Rendered site not found: {site_root}. Run the Jekyll build first.")
    return sorted(site_root.rglob("*.html"))


def _normalize_url(url: str) -> str:
    return url.rstrip(TRAILING_URL_CHARS)


def _site_hosts(paths: Paths) -> set[str]:
    config_path = paths.repo_root / "_config.yml"
    if not config_path.exists():
        return set()
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return set()
    hosts: set[str] = set()
    for key in ("url",):
        parsed = urlparse(str(payload.get(key, "")).strip())
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return hosts


def _is_internal_site_url(url: str, site_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return bool(host and host in site_hosts)


def _extract_urls(line: str) -> set[str]:
    urls = {_normalize_url(match) for match in MARKDOWN_URL_RE.findall(line)}
    urls.update(_normalize_url(match) for match in RAW_URL_RE.findall(line))
    return urls


def _record_url(
    links: dict[str, ExternalLink],
    url: str,
    path: Path,
    line_number: int,
    site_hosts: set[str],
) -> None:
    url = _normalize_url(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return
    if _is_internal_site_url(url, site_hosts):
        return
    link = links.setdefault(url, ExternalLink(url=url))
    link.occurrences.append(LinkOccurrence(path=path, line=line_number))


def collect_source_external_links(paths: Paths) -> dict[str, ExternalLink]:
    links: dict[str, ExternalLink] = {}
    site_hosts = _site_hosts(paths)
    for path in _source_content_paths(paths):
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for url in sorted(_extract_urls(line)):
                _record_url(links, url, path, line_number, site_hosts)
    return dict(sorted(links.items()))


def collect_rendered_external_link_result(paths: Paths, site_root: Path | None = None) -> LinkCollectionResult:
    root = site_root or paths.repo_root / "_site"
    links: dict[str, ExternalLink] = {}
    failures: list[LinkCollectionFailure] = []
    site_hosts = _site_hosts(paths)
    for path in _rendered_content_paths(root):
        parser = LinkHTMLParser()
        parser.feed(path.read_text(encoding="utf-8"))
        for url, line_number in parser.urls:
            _record_url(links, url, path, line_number, site_hosts)
        for line_number, message in parser.json_ld_failures:
            failures.append(LinkCollectionFailure(path=path, line=line_number, message=message))
    return LinkCollectionResult(links=dict(sorted(links.items())), failures=failures)


def collect_rendered_external_links(paths: Paths, site_root: Path | None = None) -> dict[str, ExternalLink]:
    return collect_rendered_external_link_result(paths, site_root=site_root).links


def collect_external_link_result(paths: Paths, *, source: str = DEFAULT_SOURCE, site_root: Path | None = None) -> LinkCollectionResult:
    if source == "rendered":
        return collect_rendered_external_link_result(paths, site_root=site_root)
    if source == "source":
        return LinkCollectionResult(links=collect_source_external_links(paths))
    raise ValueError(f"Unsupported link source: {source}")


def collect_external_links(paths: Paths, *, source: str = DEFAULT_SOURCE, site_root: Path | None = None) -> dict[str, ExternalLink]:
    return collect_external_link_result(paths, source=source, site_root=site_root).links


def load_allowlist(path: Path) -> list[AllowlistRule]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = payload.get("allowlist", []) if isinstance(payload, dict) else []
    loaded: list[AllowlistRule] = []
    for index, item in enumerate(rules, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: allowlist entry {index} must be a mapping.")
        match = str(item.get("match", "")).strip()
        value = str(item.get("value", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if match not in {"domain", "prefix", "exact", "regex"}:
            raise ValueError(f"{path}: allowlist entry {index} has unsupported match type {match!r}.")
        if not value:
            raise ValueError(f"{path}: allowlist entry {index} is missing value.")
        if not reason:
            raise ValueError(f"{path}: allowlist entry {index} is missing reason.")
        loaded.append(
            AllowlistRule(
                match=match,
                value=value,
                reason=reason,
                include_subdomains=bool(item.get("include_subdomains", True)),
            )
        )
    return loaded


def _matching_rule(url: str, rules: list[AllowlistRule]) -> AllowlistRule | None:
    for rule in rules:
        if rule.matches(url):
            return rule
    return None


def _first_location(link: ExternalLink, repo_root: Path) -> str:
    occurrence = link.occurrences[0]
    try:
        display_path = occurrence.path.relative_to(repo_root)
    except ValueError:
        display_path = occurrence.path
    suffix = "" if len(link.occurrences) == 1 else f" (+{len(link.occurrences) - 1} more)"
    return f"{display_path}:{occurrence.line}{suffix}"


def _collection_failure_message(failure: LinkCollectionFailure, repo_root: Path) -> str:
    try:
        display_path = failure.path.relative_to(repo_root)
    except ValueError:
        display_path = failure.path
    return f"{display_path}:{failure.line}: {failure.message}"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "shaypal5-site-link-check/1.0 (+https://github.com/shaypal5/shaypal5.github.io)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def _request_url(session: requests.Session, url: str, timeout_seconds: float) -> requests.Response:
    try:
        response = session.head(url, allow_redirects=True, timeout=timeout_seconds)
    except requests.RequestException:
        response = session.get(url, allow_redirects=True, timeout=timeout_seconds, stream=True)
    else:
        if response.status_code >= 400 and response.status_code not in SOFT_SUCCESS_STATUSES:
            response.close()
            response = session.get(url, allow_redirects=True, timeout=timeout_seconds, stream=True)
    return response


def _check_url(url: str, link: ExternalLink, paths: Paths, config: LinkCheckConfig) -> str | None:
    last_error = ""
    response: requests.Response | None = None
    session = _session()
    try:
        for attempt in range(config.retries + 1):
            try:
                response = _request_url(session, url, config.timeout_seconds)
            except requests.RequestException as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
                if attempt < config.retries:
                    continue
                return f"{_first_location(link, paths.repo_root)}: {url} failed: {last_error}"
            status = response.status_code
            response.close()
            if status < 400 or status in SOFT_SUCCESS_STATUSES:
                return None
            last_error = f"HTTP {status}"
            if attempt == config.retries:
                return f"{_first_location(link, paths.repo_root)}: {url} failed: {last_error}"
    finally:
        session.close()
    return f"{_first_location(link, paths.repo_root)}: {url} failed: {last_error}"


def check_external_links(paths: Paths, config: LinkCheckConfig) -> LinkCheckSummary:
    collection = collect_external_link_result(paths, source=config.source, site_root=config.site_root)
    links = collection.links
    rules = load_allowlist(config.allowlist_path)
    failures = [_collection_failure_message(failure, paths.repo_root) for failure in collection.failures]
    skipped_by_rule: dict[str, int] = {}
    checked = 0
    skipped = 0
    to_check: list[tuple[str, ExternalLink]] = []
    for url, link in links.items():
        rule = _matching_rule(url, rules)
        if rule is not None:
            skipped += 1
            key = f"{rule.match}:{rule.value}"
            skipped_by_rule[key] = skipped_by_rule.get(key, 0) + 1
            continue
        to_check.append((url, link))
    checked = len(to_check)
    max_workers = max(1, config.max_workers)
    if max_workers == 1:
        for url, link in to_check:
            failure = _check_url(url, link, paths, config)
            if failure:
                failures.append(failure)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(_check_url, url, link, paths, config): url for url, link in to_check
            }
            for future in as_completed(future_to_url):
                failure = future.result()
                if failure:
                    failures.append(failure)
    failures.sort()
    return LinkCheckSummary(
        checked=checked,
        skipped=skipped,
        failures=failures,
        skipped_by_rule=dict(sorted(skipped_by_rule.items())),
    )
