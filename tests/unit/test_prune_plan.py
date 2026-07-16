"""Tests for `scripts/prune_plan.py`.

The prune plan is the opt-in delete half of a team publish. These tests pin the
two safety properties (prefix-scoping and desired-state exclusion) plus the
config/build-root plumbing and the CLI entrypoints.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _make_script_importable() -> None:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _mod():
    import importlib

    import prune_plan

    importlib.reload(prune_plan)
    return prune_plan


_CONFIG = (
    '{"teams":['
    '{"name":"team-a","folder":"apim-config/workspaces/pensions-core/teams/team-a","prefix":"teama"},'
    '{"name":"team-b","folder":"apim-config/workspaces/pensions-core/teams/team-b","prefix":"teamb"}'
    "]}"
)


def _config(tmp_path: Path) -> Path:
    cfg = tmp_path / "ci.json"
    cfg.write_text(_CONFIG, encoding="utf-8")
    return cfg


def _build_with(tmp_path: Path, workspace: str, native_subdir: str, names: list[str]) -> Path:
    root = tmp_path / "build"
    kind_dir = root / "workspaces" / workspace / native_subdir
    for name in names:
        (kind_dir / name).mkdir(parents=True)
    return root


# --------------------------------------------------------------------------- #
# pure functions
# --------------------------------------------------------------------------- #
def test_team_meta_resolves_workspace_and_prefix(tmp_path: Path) -> None:
    pp = _mod()
    config = pp.load_config(_config(tmp_path))
    assert pp.team_meta(config, "team-a") == ("pensions-core", "teama")
    assert pp.team_meta(config, "team-b") == ("pensions-core", "teamb")


def test_team_meta_unknown_team_raises(tmp_path: Path) -> None:
    pp = _mod()
    config = pp.load_config(_config(tmp_path))
    with pytest.raises(KeyError):
        pp.team_meta(config, "team-z")


def test_desired_names_reads_native_subdirs(tmp_path: Path) -> None:
    pp = _mod()
    build = _build_with(tmp_path, "pensions-core", "apis", ["teama-orders-v1", "teama-payments-v1"])
    assert pp.desired_names(build, "pensions-core", "apis") == {
        "teama-orders-v1",
        "teama-payments-v1",
    }


def test_desired_names_uses_spaced_folder_for_named_values(tmp_path: Path) -> None:
    pp = _mod()
    build = _build_with(tmp_path, "pensions-core", "named values", ["teama-orders-api-key"])
    assert pp.desired_names(build, "pensions-core", "namedValues") == {"teama-orders-api-key"}


def test_desired_names_missing_dir_is_empty(tmp_path: Path) -> None:
    pp = _mod()
    assert pp.desired_names(tmp_path / "nope", "pensions-core", "apis") == set()


def test_plan_deletions_prunes_live_not_desired() -> None:
    pp = _mod()
    live = ["teama-orders-v1", "teama-payments-v1"]
    desired = {"teama-orders-v1"}
    assert pp.plan_deletions(live, desired, "teama") == ["teama-payments-v1"]


def test_plan_deletions_never_touches_other_prefixes() -> None:
    pp = _mod()
    # team-b + shared resources are live but must never be prune candidates.
    live = ["teamb-claims-v1", "contoso-orders-canonical-v1", "teama-orders-v1"]
    desired: set[str] = set()  # team-a declares nothing
    assert pp.plan_deletions(live, desired, "teama") == ["teama-orders-v1"]


def test_plan_deletions_prefix_boundary_not_substring() -> None:
    pp = _mod()
    # 'teamaccount-x' must NOT match prefix 'teama' (boundary is 'teama-').
    live = ["teamaccount-x", "teama-orders-v1"]
    assert pp.plan_deletions(live, set(), "teama") == ["teama-orders-v1"]


def test_plan_deletions_dedupes() -> None:
    pp = _mod()
    live = ["teama-x", "teama-x"]
    assert pp.plan_deletions(live, set(), "teama") == ["teama-x"]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_meta_prints_tab_separated(tmp_path: Path, capsys) -> None:
    pp = _mod()
    rc = pp.main(["meta", "--config", str(_config(tmp_path)), "--team", "team-a"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == "pensions-core\tteama"


def test_cli_plan_from_file(tmp_path: Path, capsys) -> None:
    pp = _mod()
    build = _build_with(tmp_path, "pensions-core", "apis", ["teama-orders-v1"])
    live = tmp_path / "live.txt"
    live.write_text("teama-orders-v1\nteama-payments-v1\nteamb-claims-v1\n", encoding="utf-8")
    rc = pp.main(
        [
            "plan",
            "--config",
            str(_config(tmp_path)),
            "--team",
            "team-a",
            "--build-root",
            str(build),
            "--kind",
            "apis",
            "--live",
            str(live),
        ]
    )
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == "teama-payments-v1"


def test_cli_plan_from_stdin(tmp_path: Path, capsys, monkeypatch) -> None:
    pp = _mod()
    build = _build_with(tmp_path, "pensions-core", "apis", [])
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("teama-orders-v1\n"))
    rc = pp.main(
        [
            "plan",
            "--config",
            str(_config(tmp_path)),
            "--team",
            "team-a",
            "--build-root",
            str(build),
            "--kind",
            "apis",
            "--live",
            "-",
        ]
    )
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == "teama-orders-v1"
