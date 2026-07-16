"""versioning: every API specification must declare ``info.version`` and, if
marked deprecated, must carry an ``x-deprecation-date`` in the future or up to
the PDF-defined minimum support window in the past.

Source: PDF §"Versioning Breaking Changes":

- "Every breaking change requires a new API version"
- "Older versions must have a documented deprecation date"
- "A minimum support window (e.g., 6–12 months) should be agreed per API tier"

This check is intentionally pragmatic: it enforces the *metadata* discipline
(the contract version is recorded, deprecation dates exist when needed) at PR
time. The deprecation-window enforcement per tier lives in the API consumer's
own governance process; here we just refuse a missing or syntactically
invalid date.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import yaml

from _common import (
    CIConfig,
    Violation,
    build_arg_parser,
    emit,
    filter_existing,
    load_config,
    read_changed_files,
)


def _is_spec_file(path: str) -> bool:
    parts = path.split("/")
    return "apis" in parts and path.lower().endswith(("specification.yaml", "specification.yml"))


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    spec_files = [p for p in changed_files if _is_spec_file(p)]
    for rel_path in filter_existing(spec_files, repo_root):
        text = (Path(repo_root) / rel_path).read_text(encoding="utf-8")
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            violations.append(
                Violation(
                    rule="versioning",
                    path=rel_path,
                    message=f"specification is not valid YAML: {exc}",
                )
            )
            continue
        if not isinstance(payload, dict):
            violations.append(
                Violation(
                    rule="versioning",
                    path=rel_path,
                    message="OpenAPI document must be a mapping at the top level",
                )
            )
            continue
        info = payload.get("info")
        if not isinstance(info, dict) or not isinstance(info.get("version"), str) or not info["version"].strip():
            violations.append(
                Violation(
                    rule="versioning",
                    path=rel_path,
                    message="info.version is required (PDF §Versioning Breaking Changes).",
                )
            )
            continue
        is_deprecated = bool(payload.get("deprecated")) or bool(info.get("x-deprecated"))
        deprecation_field = info.get("x-deprecation-date")
        if is_deprecated:
            parsed = _parse_iso_date(deprecation_field)
            if parsed is None:
                violations.append(
                    Violation(
                        rule="versioning",
                        path=rel_path,
                        message=(
                            "API is marked deprecated but info.x-deprecation-date "
                            "is missing or not an ISO-8601 date (YYYY-MM-DD)."
                        ),
                    )
                )
                continue
        elif deprecation_field is not None and not isinstance(deprecation_field, str):
            # Allow explicit null, reject other malformed values.
            violations.append(
                Violation(
                    rule="versioning",
                    path=rel_path,
                    message="info.x-deprecation-date must be null or an ISO-8601 string.",
                )
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser(__doc__ or "")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    changed = read_changed_files(args.changed_files)
    return emit(check(changed, args.repo_root, config))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
