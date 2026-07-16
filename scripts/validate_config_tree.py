"""validate_config_tree: smoke-validate that every file under apim-config/
parses as the format its extension implies.

This is a stand-in for the real APIOps publisher dry-run. It is intentionally
strict about JSON/YAML/XML well-formedness so the publisher workflow fails
fast if a merge accidentally pushes a malformed file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from lxml import etree


def _validate_one(path: Path) -> str | None:
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"unreadable: {exc}"
    try:
        if suffix == ".json":
            json.loads(text)
        elif suffix in (".yaml", ".yml"):
            yaml.safe_load(text)
        elif suffix == ".xml":
            etree.fromstring(text.encode("utf-8"))
    except (json.JSONDecodeError, yaml.YAMLError, etree.XMLSyntaxError) as exc:
        return str(exc)
    return None


def validate(root: Path) -> list[tuple[Path, str]]:
    failures: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".yaml", ".yml", ".xml"}:
            continue
        err = _validate_one(path)
        if err is not None:
            failures.append((path, err))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="apim-config root to validate")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.exists():
        print(f"root path '{root}' does not exist", file=sys.stderr)
        return 2
    failures = validate(root)
    for p, err in failures:
        print(f"FAIL {p}: {err}", file=sys.stderr)
    if failures:
        print(f"\n{len(failures)} malformed file(s).", file=sys.stderr)
        return 1
    print("All files well-formed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
