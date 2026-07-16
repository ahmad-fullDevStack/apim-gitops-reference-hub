"""secret_scan: a named-value definition must reference a Key Vault, not
contain a literal secret value.

This is a narrow, deterministic check that runs only against named-value JSON
files. It is intentionally **not** a general-purpose secret scanner (use
``gh secret-scanning`` or ``gitleaks`` for that, configured at the repo
ruleset layer). The intent here is to fail fast on the most common APIM
config mistake: pasting a string into ``value`` instead of using
``keyVault.secretIdentifier``.

A named-value is either:

- ``properties.value`` (the ARM template shape), or
- ``value`` (the APIOps simplified shape).

Either with a non-empty string ``value`` is rejected unless the file also
declares ``properties.keyVault.secretIdentifier`` / ``keyVault.secretIdentifier``
*and* the ``value`` field is exactly the empty string (a common APIOps
artefact that is harmless).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from _common import (
    CIConfig,
    Violation,
    build_arg_parser,
    emit,
    filter_existing,
    load_config,
    read_changed_files,
)


def _is_named_value_file(path: str) -> bool:
    parts = path.split("/")
    return "named-values" in parts and path.lower().endswith(".json")


def _has_kv_reference(payload: dict[str, object]) -> bool:
    kv = payload.get("keyVault")
    if isinstance(kv, dict):
        sid = kv.get("secretIdentifier")
        if isinstance(sid, str) and sid:
            return True
    props = payload.get("properties")
    if isinstance(props, dict):
        kv2 = props.get("keyVault")
        if isinstance(kv2, dict):
            sid2 = kv2.get("secretIdentifier")
            if isinstance(sid2, str) and sid2:
                return True
    return False


def _literal_value(payload: dict[str, object]) -> str | None:
    candidates: list[object] = [payload.get("value")]
    props = payload.get("properties")
    if isinstance(props, dict):
        candidates.append(props.get("value"))
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c
    return None


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    nv_files = [p for p in changed_files if _is_named_value_file(p)]
    for rel_path in filter_existing(nv_files, repo_root):
        try:
            payload = json.loads((Path(repo_root) / rel_path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append(
                Violation(
                    rule="secret-scan",
                    path=rel_path,
                    message=f"named-value is not valid JSON: {exc.msg}",
                )
            )
            continue
        if not isinstance(payload, dict):
            violations.append(
                Violation(
                    rule="secret-scan",
                    path=rel_path,
                    message="named-value must be a JSON object",
                )
            )
            continue
        is_secret = bool(payload.get("secret"))
        props = payload.get("properties")
        if isinstance(props, dict) and props.get("secret"):
            is_secret = True
        literal = _literal_value(payload)
        if literal is None:
            continue  # nothing to flag
        if is_secret:
            violations.append(
                Violation(
                    rule="secret-scan",
                    path=rel_path,
                    message=(
                        "named-value is marked secret but contains a literal value; "
                        "use keyVault.secretIdentifier instead."
                    ),
                )
            )
            continue
        if _has_kv_reference(payload):
            violations.append(
                Violation(
                    rule="secret-scan",
                    path=rel_path,
                    message=(
                        "named-value declares both a literal value and a Key Vault "
                        "reference; remove the literal value."
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
