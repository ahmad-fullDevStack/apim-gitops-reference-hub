"""inventory: scan the entire apim-config tree for duplicate backend URLs and
near-duplicate policies across teams and workspaces.

Source: PDF §"Workspace Consolidation Roadmap → Phase 1 — Discovery &
Inventory":

- "Detect duplicate APIs: identify APIs with identical or similar backend URLs
  across different workspaces."
- "Detect policy drift: compare policies that differ only slightly between
  copies of the same API."

This script is **report-only** — it never fails CI. It is intended to run on
schedule (alongside extractor-drift.yml) and post its findings as a workflow
artifact so the platform team can prioritise the "top 5–10 most-consumed APIs
to deduplicate first" (PDF §Immediate Stabilization Measures #3).

Run with ``python .github/scripts/inventory.py --apim-config apim-config/`` to
produce a JSON report on stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def _backend_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.json") if "backends" in p.parts)


def _policy_files(root: Path) -> list[Path]:
    return sorted(root.rglob("policy.xml"))


def _read_url(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    url = payload.get("url")
    if isinstance(url, str):
        return url.strip().lower()
    props = payload.get("properties")
    if isinstance(props, dict):
        prop_url = props.get("url")
        if isinstance(prop_url, str):
            return prop_url.strip().lower()
    return None


_NORMALISE = re.compile(r"\s+")


def _policy_fingerprint(text: str) -> str:
    """SHA1 of whitespace-normalised policy contents (proxy for near-duplicates)."""
    normalised = _NORMALISE.sub(" ", text).strip()
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()  # nosec B324  # not a security context


def scan(root: Path) -> dict[str, object]:
    duplicate_backends: dict[str, list[str]] = defaultdict(list)
    for path in _backend_files(root):
        url = _read_url(path)
        if url is None:
            continue
        duplicate_backends[url].append(str(path.relative_to(root)).replace("\\", "/"))
    duplicates = {url: paths for url, paths in duplicate_backends.items() if len(paths) > 1}

    policy_buckets: dict[str, list[str]] = defaultdict(list)
    for path in _policy_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fp = _policy_fingerprint(text)
        policy_buckets[fp].append(str(path.relative_to(root)).replace("\\", "/"))
    policy_duplicates = {fp: paths for fp, paths in policy_buckets.items() if len(paths) > 1}

    return {
        "duplicate_backend_urls": duplicates,
        "duplicate_policies": policy_duplicates,
        "summary": {
            "backend_files_scanned": len(_backend_files(root)),
            "policy_files_scanned": len(_policy_files(root)),
            "duplicate_backend_count": len(duplicates),
            "duplicate_policy_count": len(policy_duplicates),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apim-config",
        default="apim-config",
        help="Path to apim-config/ root (default: apim-config)",
    )
    args = parser.parse_args(argv)
    root = Path(args.apim_config)
    if not root.is_dir():
        print(f"apim-config root '{root}' does not exist", file=sys.stderr)
        return 2
    report = scan(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
