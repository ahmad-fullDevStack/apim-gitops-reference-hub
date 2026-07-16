"""Tests for `run_all` orchestrator and `validate_config_tree` script."""

from __future__ import annotations

from pathlib import Path

import pytest
import run_all


def _ci_config_json(tmp_path: Path) -> Path:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces",'
        '"platform_paths":["apim-config/service"],'
        '"domains":[{"name":"pensions-core","tier":"gold","leads_team":"pc-leads","active":true}],'
        '"valid_tiers":["gold","silver","bronze"],'
        '"teams":[{"name":"team-a",'
        '"folder":"apim-config/workspaces/pensions-core/teams/team-a","prefix":"teama",'
        '"allowed_key_vaults":["kv-team-a"],"allowed_backend_hosts":["ok.invalid"]}]}',
        encoding="utf-8",
    )
    return cfg


def test_clean_pr_passes(tmp_path: Path, capsys, monkeypatch) -> None:
    cfg = _ci_config_json(tmp_path)
    p = tmp_path / "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
    p.parent.mkdir(parents=True)
    p.write_text(
        "<?xml version='1.0'?><policies>"
        "<inbound><base /></inbound>"
        "<backend><base /></backend>"
        "<outbound><base /></outbound>"
        "<on-error><base /></on-error>"
        "</policies>",
        encoding="utf-8",
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = run_all.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert "PASS" in captured.out


def test_failing_pr_reports_each_failing_check_once(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg = _ci_config_json(tmp_path)
    p_bad = (
        tmp_path
        / "apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-x/policy.xml"
    )
    p_bad.parent.mkdir(parents=True)
    p_bad.write_text(
        "<?xml version='1.0'?><policies><inbound>"
        "<set-header name='x' exists-action='override'><value>v</value></set-header>"
        "</inbound></policies>",
        encoding="utf-8",
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-x/policy.xml\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = run_all.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "base-inheritance" in captured.out  # section header is on stdout
    assert "naming-convention" in captured.out
    assert "violation(s)" in captured.out or "violation(s)" in captured.err


def test_new_checks_are_wired_in(tmp_path: Path, capsys, monkeypatch) -> None:
    """tier-check, freeze-workspace, versioning all appear in the orchestrator output."""
    cfg = _ci_config_json(tmp_path)
    changed = tmp_path / "changed.txt"
    changed.write_text("README.md\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = run_all.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert rc == 0
    for name in ("tier-check", "freeze-workspace", "versioning"):
        assert name in out


def test_run_all_handles_check_crash_via_uncaught_exception(
    tmp_path: Path, monkeypatch
) -> None:
    """`run_all.run` does not catch exceptions; propagation is the contract."""
    cfg = _ci_config_json(tmp_path)
    changed = tmp_path / "changed.txt"
    changed.write_text("README.md\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def _boom(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        run_all,
        "_CHECKS",
        (("crasher", _boom),),
    )

    with pytest.raises(RuntimeError, match="boom"):
        run_all.main(
            ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
        )
