from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.config import build_paths, repo_root
from automation.data_io import format_teaching_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Format canonical teaching YAML files deterministically.")
    parser.add_argument("--check", action="store_true", help="Fail if any teaching YAML file would be reformatted.")
    args = parser.parse_args()

    paths = build_paths(repo_root())
    changed = format_teaching_yaml(paths, check=args.check)
    if not changed:
        print("Teaching YAML formatting is up to date.")
        return 0

    for path in changed:
        print(path)
    if args.check:
        print(f"{len(changed)} teaching YAML file(s) need formatting.", file=sys.stderr)
        return 1

    print(f"Formatted {len(changed)} teaching YAML file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
