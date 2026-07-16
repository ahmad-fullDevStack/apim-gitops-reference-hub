"""Shared types and helpers for APIM-config CI checks.

All check modules build on this. Keeping it small and dependency-free makes
the unit tests trivial and the scripts portable to Azure DevOps or any other
CI system without modification.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """A single CI policy violation."""

    rule: str
    path: str
    message: str

    def format(self) -> str:
        return f"[{self.rule}] {self.path}: {self.message}"


@dataclass
class TeamConfig:
    """Per-team configuration loaded from ``config/teams.yaml``."""

    name: str
    folder: str
    prefix: str
    allowed_key_vaults: list[str] = field(default_factory=list)
    allowed_backend_hosts: list[str] = field(default_factory=list)


@dataclass
class DomainConfig:
    """Per-domain (workspace) configuration."""

    name: str
    tier: str
    leads_team: str
    active: bool = False


_DEFAULT_VALID_TIERS: tuple[str, ...] = ("gold", "silver", "bronze")


@dataclass
class GatewayCapacity:
    """Documented APIM gateway limits used by capacity checks."""

    workspaces_per_instance: int = 100
    workspaces_per_gateway: int = 30
    target_active_workspaces: int = 10


@dataclass
class CIConfig:
    """Top-level CI configuration."""

    workspace_root: str  # e.g. "apim-config/workspaces"
    platform_paths: list[str] = field(default_factory=list)
    teams: list[TeamConfig] = field(default_factory=list)
    domains: list[DomainConfig] = field(default_factory=list)
    valid_tiers: list[str] = field(default_factory=lambda: list(_DEFAULT_VALID_TIERS))
    gateway_capacity: GatewayCapacity = field(default_factory=GatewayCapacity)

    def team_for_path(self, repo_relative_path: str) -> TeamConfig | None:
        """Return the team that owns ``repo_relative_path``, or ``None``."""
        normalised = repo_relative_path.replace("\\", "/")
        for team in self.teams:
            if normalised.startswith(team.folder.rstrip("/") + "/"):
                return team
        return None

    def is_platform_path(self, repo_relative_path: str) -> bool:
        normalised = repo_relative_path.replace("\\", "/")
        return any(
            normalised.startswith(p.rstrip("/") + "/") or normalised == p
            for p in self.platform_paths
        )

    def domain_for_workspace_dir(self, workspace_dir_name: str) -> DomainConfig | None:
        for d in self.domains:
            if d.name == workspace_dir_name:
                return d
        return None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = Path("config/ci.json")


def load_config(path: str | Path | None = None) -> CIConfig:
    """Load :class:`CIConfig` from a JSON file.

    YAML support is intentionally omitted to keep this dependency-free; the
    file lives in the repo as JSON for the same reason.
    """
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not cfg_path.is_file():
        raise FileNotFoundError(f"CI config not found at {cfg_path}")
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    teams = [
        TeamConfig(
            name=t["name"],
            folder=t["folder"],
            prefix=t["prefix"],
            allowed_key_vaults=list(t.get("allowed_key_vaults", [])),
            allowed_backend_hosts=list(t.get("allowed_backend_hosts", [])),
        )
        for t in data.get("teams", [])
    ]
    domains = [
        DomainConfig(
            name=d["name"],
            tier=d["tier"],
            leads_team=d["leads_team"],
            active=bool(d.get("active", False)),
        )
        for d in data.get("domains", [])
    ]
    gw_raw = data.get("gateway_capacity") or {}
    gateway_capacity = GatewayCapacity(
        workspaces_per_instance=int(gw_raw.get("workspaces_per_instance", 100)),
        workspaces_per_gateway=int(gw_raw.get("workspaces_per_gateway", 30)),
        target_active_workspaces=int(gw_raw.get("target_active_workspaces", 10)),
    )
    return CIConfig(
        workspace_root=data["workspace_root"],
        platform_paths=list(data.get("platform_paths", [])),
        teams=teams,
        domains=domains,
        valid_tiers=list(data.get("valid_tiers", _DEFAULT_VALID_TIERS)),
        gateway_capacity=gateway_capacity,
    )


# ---------------------------------------------------------------------------
# Changed-file discovery
# ---------------------------------------------------------------------------


def read_changed_files(source: str | Path | None) -> list[str]:
    """Read changed-file list from a file path or stdin.

    Each line is treated as one path. Blank lines and lines starting with ``#``
    are ignored. Paths are returned in repo-relative POSIX form.
    """
    if source is None or str(source) == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(source).read_text(encoding="utf-8")
    return [
        line.strip().replace("\\", "/")
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ---------------------------------------------------------------------------
# CLI plumbing shared by all check modules
# ---------------------------------------------------------------------------


def build_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--changed-files",
        help="Path to a file listing changed paths (one per line). '-' for stdin.",
        default="-",
    )
    parser.add_argument(
        "--config",
        help="Path to CI config JSON. Defaults to config/ci.json.",
        default=None,
    )
    parser.add_argument(
        "--repo-root",
        help="Repository root. Defaults to current working directory.",
        default=".",
    )
    return parser


def emit(violations: Sequence[Violation], stream: TextIO | None = None) -> int:
    """Print violations and return the exit code (0 if none, 1 otherwise).

    ``stream`` defaults to the current ``sys.stdout`` (looked up at call time
    so test harnesses that swap stdout see the output).
    """
    target = stream if stream is not None else sys.stdout
    for v in violations:
        print(v.format(), file=target)
    if violations:
        print(f"\n{len(violations)} violation(s) found.", file=target)
        return 1
    return 0


# ---------------------------------------------------------------------------
# Small reusable predicates
# ---------------------------------------------------------------------------


_KV_URI_RE = re.compile(
    r"https://(?P<vault>[a-z0-9][a-z0-9-]{1,22}[a-z0-9])\.vault\.azure\.net/",
    re.IGNORECASE,
)


def extract_kv_hostnames(text: str) -> list[str]:
    """Return all Key Vault DNS prefixes referenced in ``text``."""
    return [m.group("vault").lower() for m in _KV_URI_RE.finditer(text)]


def under_workspace_teams(path: str, workspace_root: str) -> bool:
    """True if ``path`` lives under ``<workspace_root>/<ws>/teams/``."""
    normalised = path.replace("\\", "/")
    root = workspace_root.rstrip("/")
    if not normalised.startswith(root + "/"):
        return False
    remainder = normalised[len(root) + 1 :].split("/")
    return len(remainder) >= 3 and remainder[1] == "teams"


def filter_existing(paths: Iterable[str], repo_root: str | Path) -> list[str]:
    """Return only paths that exist on disk (deleted files are skipped)."""
    base = Path(repo_root)
    return [p for p in paths if (base / p).is_file()]
