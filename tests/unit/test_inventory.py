"""Tests for `inventory` (Phase 1 discovery / dedup detection)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import inventory


def _write(p: Path, content: str | dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        p.write_text(json.dumps(content), encoding="utf-8")
    else:
        p.write_text(content, encoding="utf-8")


def test_scan_finds_duplicate_backends(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspaces/x/backends/a.json",
        {"name": "a", "properties": {"url": "https://api.contoso.com/x"}},
    )
    _write(
        tmp_path / "workspaces/y/backends/b.json",
        {"name": "b", "properties": {"url": "https://API.contoso.com/X"}},
    )
    _write(
        tmp_path / "workspaces/z/backends/c.json",
        {"name": "c", "url": "https://other.invalid/"},
    )
    report = inventory.scan(tmp_path)
    dups = report["duplicate_backend_urls"]
    assert "https://api.contoso.com/x" in dups
    assert len(dups["https://api.contoso.com/x"]) == 2


def test_scan_finds_duplicate_policies(tmp_path: Path) -> None:
    body = (
        "<?xml version='1.0'?><policies><inbound><base /></inbound></policies>"
    )
    _write(tmp_path / "workspaces/x/teams/a/apis/o/policy.xml", body)
    _write(tmp_path / "workspaces/x/teams/b/apis/o/policy.xml", "  " + body + "\n")
    report = inventory.scan(tmp_path)
    assert len(report["duplicate_policies"]) == 1


def test_scan_skips_invalid_json_backends(tmp_path: Path) -> None:
    _write(tmp_path / "workspaces/x/backends/bad.json", "{not json")
    report = inventory.scan(tmp_path)
    assert report["duplicate_backend_urls"] == {}


def test_scan_skips_non_dict_json(tmp_path: Path) -> None:
    _write(tmp_path / "workspaces/x/backends/list.json", "[]")
    report = inventory.scan(tmp_path)
    assert report["duplicate_backend_urls"] == {}


def test_scan_skips_backend_without_url(tmp_path: Path) -> None:
    _write(tmp_path / "workspaces/x/backends/a.json", {"name": "a"})
    _write(tmp_path / "workspaces/x/backends/b.json", {"name": "b", "properties": {}})
    report = inventory.scan(tmp_path)
    assert report["duplicate_backend_urls"] == {}


def test_summary_counts(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspaces/x/backends/a.json",
        {"name": "a", "url": "https://api/"},
    )
    _write(
        tmp_path / "workspaces/y/backends/b.json",
        {"name": "b", "url": "https://api/"},
    )
    _write(
        tmp_path / "workspaces/x/teams/a/apis/o/policy.xml",
        "<policies><inbound><base /></inbound></policies>",
    )
    report = inventory.scan(tmp_path)
    s = report["summary"]
    assert s["backend_files_scanned"] == 2
    assert s["policy_files_scanned"] == 1
    assert s["duplicate_backend_count"] == 1
    assert s["duplicate_policy_count"] == 0


def test_main_writes_report(tmp_path: Path, capsys) -> None:
    _write(
        tmp_path / "workspaces/x/backends/a.json",
        {"name": "a", "url": "https://api/"},
    )
    rc = inventory.main(["--apim-config", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "duplicate_backend_urls" in out


def test_main_returns_two_on_missing_root(tmp_path: Path, capsys) -> None:
    rc = inventory.main(["--apim-config", str(tmp_path / "nope")])
    assert rc == 2
    assert "does not exist" in capsys.readouterr().err


def test_scan_skips_unreadable_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers the OSError branch on policy.xml read in inventory.scan."""
    _write(
        tmp_path / "workspaces/x/teams/a/apis/o/policy.xml",
        "<policies><inbound><base /></inbound></policies>",
    )

    real_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "policy.xml":
            raise OSError("simulated unreadable file")
        return real_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    report = inventory.scan(tmp_path)
    # No policy was readable, so no duplicate group exists.
    assert report["duplicate_policies"] == {}
