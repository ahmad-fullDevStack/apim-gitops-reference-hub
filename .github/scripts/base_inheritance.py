"""base_inheritance: every APIM ``policy.xml`` must include ``<base />`` in
each of the four policy sections that allow it (``inbound``, ``backend``,
``outbound``, ``on-error``).

This mirrors the Azure built-in policy
`API Management policies should inherit parent scope policies using <base/>`
but enforces it at PR time so a missing ``<base />`` never reaches APIM.
"""

from __future__ import annotations

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
from lxml import etree

REQUIRED_SECTIONS: tuple[str, ...] = ("inbound", "backend", "outbound", "on-error")


def _policy_files(changed: Sequence[str]) -> list[str]:
    return [p for p in changed if p.lower().endswith("policy.xml")]


def _has_base(section_element: etree._Element) -> bool:
    return any(child.tag == "base" for child in section_element)


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    for rel_path in filter_existing(_policy_files(changed_files), repo_root):
        abs_path = Path(repo_root) / rel_path
        try:
            tree = etree.parse(str(abs_path))
        except etree.XMLSyntaxError as exc:
            violations.append(
                Violation(
                    rule="base-inheritance",
                    path=rel_path,
                    message=f"policy.xml is not well-formed XML: {exc.msg}",
                )
            )
            continue
        root = tree.getroot()
        if root.tag != "policies":
            violations.append(
                Violation(
                    rule="base-inheritance",
                    path=rel_path,
                    message="root element must be <policies>",
                )
            )
            continue
        present_sections = {child.tag: child for child in root if isinstance(child.tag, str)}
        for section_name in REQUIRED_SECTIONS:
            if section_name not in present_sections:
                continue  # absent section is allowed; only missing <base/> in a present section is a violation
            if not _has_base(present_sections[section_name]):
                violations.append(
                    Violation(
                        rule="base-inheritance",
                        path=rel_path,
                        message=(
                            f"<{section_name}> is present but does not include <base />; "
                            "parent-scope policy would be bypassed at runtime."
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
