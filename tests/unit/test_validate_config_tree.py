"""Tests for `scripts/validate_config_tree.py`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _make_script_importable() -> None:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _vct():
    import importlib

    import validate_config_tree

    importlib.reload(validate_config_tree)
    return validate_config_tree


def test_well_formed_tree_passes(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(json.dumps({"k": "v"}), encoding="utf-8")
    (tmp_path / "b.yaml").write_text("k: v\n", encoding="utf-8")
    (tmp_path / "c.xml").write_text("<root/>", encoding="utf-8")
    (tmp_path / "d.txt").write_text("ignored", encoding="utf-8")
    failures = _vct().validate(tmp_path)
    assert failures == []


def test_malformed_json_fails(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    failures = _vct().validate(tmp_path)
    assert len(failures) == 1
    assert failures[0][0].name == "bad.json"


def test_malformed_yaml_fails(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text("key: : :\n", encoding="utf-8")
    failures = _vct().validate(tmp_path)
    assert len(failures) == 1
    assert failures[0][0].name == "bad.yaml"


def test_malformed_xml_fails(tmp_path: Path) -> None:
    (tmp_path / "bad.xml").write_text("<not-closed>", encoding="utf-8")
    failures = _vct().validate(tmp_path)
    assert len(failures) == 1
    assert failures[0][0].name == "bad.xml"


def test_yml_extension_also_handled(tmp_path: Path) -> None:
    (tmp_path / "good.yml").write_text("k: v\n", encoding="utf-8")
    assert _vct().validate(tmp_path) == []


def test_main_returns_zero_when_clean(tmp_path: Path, capsys) -> None:
    (tmp_path / "ok.json").write_text("{}", encoding="utf-8")
    rc = _vct().main([str(tmp_path)])
    assert rc == 0
    assert "well-formed" in capsys.readouterr().out


def test_main_returns_one_when_failures(tmp_path: Path, capsys) -> None:
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    rc = _vct().main([str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "bad.json" in captured.err


def test_main_errors_when_root_missing(tmp_path: Path, capsys) -> None:
    rc = _vct().main([str(tmp_path / "nope")])
    assert rc == 2
    assert "does not exist" in capsys.readouterr().err


def test_directory_inside_tree_is_skipped(tmp_path: Path) -> None:
    """`validate()` walks rglob('*') which includes directories; they must be skipped."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "ok.json").write_text("{}", encoding="utf-8")
    assert _vct().validate(tmp_path) == []


def test_validate_one_unknown_suffix_returns_none(tmp_path: Path) -> None:
    """`_validate_one` is reachable directly; non-recognised suffix yields None."""
    p = tmp_path / "x.unknown"
    p.write_text("anything", encoding="utf-8")
    assert _vct()._validate_one(p) is None


def test_validate_one_unreadable_file(tmp_path: Path, monkeypatch) -> None:
    """Simulate a read failure to cover the OSError branch."""
    p = tmp_path / "x.json"
    p.write_text("{}", encoding="utf-8")

    def _boom(self, *_a, **_kw):
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_text", _boom)
    msg = _vct()._validate_one(p)
    assert msg is not None
    assert "unreadable" in msg
