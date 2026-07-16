"""Shared pytest fixtures for the CI-script unit tests.

Each test gets a temp directory laid out like the real repository, plus a
:class:`CIConfig` that points at it. This keeps tests hermetic and lets us
exercise every branch of every script without ever touching the real repo.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from _common import CIConfig, TeamConfig


@pytest.fixture
def ci_config() -> CIConfig:
    return CIConfig(
        workspace_root="apim-config/workspaces",
        platform_paths=[
            "apim-config/service",
            "apim-config/workspaces/pensions-core/workspace.json",
            "apim-config/workspaces/pensions-core/policy.xml",
        ],
        teams=[
            TeamConfig(
                name="team-a",
                folder="apim-config/workspaces/pensions-core/teams/team-a",
                prefix="teama",
                allowed_key_vaults=["kv-pensions-core-team-a"],
                allowed_backend_hosts=[
                    "stub-orders-api.azurewebsites.net",
                    "orders.contoso.com",
                ],
            ),
            TeamConfig(
                name="team-b",
                folder="apim-config/workspaces/pensions-core/teams/team-b",
                prefix="teamb",
                allowed_key_vaults=["kv-pensions-core-team-b"],
                allowed_backend_hosts=["claims.contoso.com"],
            ),
        ],
    )


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    """A throwaway directory laid out like the project root."""
    # Pre-create the standard tree so write helpers don't have to.
    (tmp_path / "apim-config" / "workspaces" / "pensions-core" / "teams" / "team-a").mkdir(
        parents=True
    )
    (tmp_path / "apim-config" / "workspaces" / "pensions-core" / "teams" / "team-b").mkdir(
        parents=True
    )
    yield tmp_path


def write(path: Path, content: str | dict) -> None:
    """Write ``content`` to ``path``, creating parents and serialising dicts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")
