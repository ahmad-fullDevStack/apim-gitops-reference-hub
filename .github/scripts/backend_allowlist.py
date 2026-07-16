"""backend_allowlist: backend definitions under a team's folder must reference
hosts on that team's allowlist.

A backend is a JSON file under ``backends/`` whose ``url`` (or
``properties.url``) is checked. Hostname is extracted and matched against the
team's ``allowed_backend_hosts`` list.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from _common import (
    CIConfig,
    Violation,
    build_arg_parser,
    emit,
    filter_existing,
    load_config,
    read_changed_files,
)


def _is_backend_file(path: str) -> bool:
    parts = path.split("/")
    return "backends" in parts and path.lower().endswith(".json")


def _extract_url(payload: dict[str, object]) -> str | None:
    url = payload.get("url")
    if isinstance(url, str):
        return url
    properties = payload.get("properties")
    if isinstance(properties, dict):
        prop_url = properties.get("url")
        if isinstance(prop_url, str):
            return prop_url
    return None


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    backend_files = [p for p in changed_files if _is_backend_file(p)]
    for rel_path in filter_existing(backend_files, repo_root):
        team = config.team_for_path(rel_path)
        if team is None:
            continue
        try:
            payload = json.loads((Path(repo_root) / rel_path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append(
                Violation(
                    rule="backend-allowlist",
                    path=rel_path,
                    message=f"backend definition is not valid JSON: {exc.msg}",
                )
            )
            continue
        if not isinstance(payload, dict):
            violations.append(
                Violation(
                    rule="backend-allowlist",
                    path=rel_path,
                    message="backend definition must be a JSON object",
                )
            )
            continue
        url = _extract_url(payload)
        if url is None:
            violations.append(
                Violation(
                    rule="backend-allowlist",
                    path=rel_path,
                    message="backend definition is missing a 'url' (or 'properties.url') field",
                )
            )
            continue
        parsed = urlparse(url)
        if not parsed.hostname:
            violations.append(
                Violation(
                    rule="backend-allowlist",
                    path=rel_path,
                    message=f"backend url '{url}' has no hostname",
                )
            )
            continue
        host = parsed.hostname.lower()
        allowed = {h.lower() for h in team.allowed_backend_hosts}
        if host not in allowed:
            violations.append(
                Violation(
                    rule="backend-allowlist",
                    path=rel_path,
                    message=(
                        f"team '{team.name}' is not allowed to call backend host "
                        f"'{host}'. Allowlist: {sorted(team.allowed_backend_hosts)}"
                    ),
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
