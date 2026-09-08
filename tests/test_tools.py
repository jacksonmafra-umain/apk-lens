from __future__ import annotations

import json

import pytest

from apk_lens import console, tools
from apk_lens.cli import main


@pytest.fixture
def fake_path(monkeypatch):
    """Pretend a chosen set of executables exists on PATH."""
    installed: dict[str, str] = {}

    def which(name):
        return installed.get(name)

    def probe(executable, spec):
        return "1.2.3"

    monkeypatch.setattr(tools.shutil, "which", which)
    monkeypatch.setattr(tools, "_probe_version", probe)
    return installed


def test_missing_tool_is_reported_as_not_found(fake_path):
    status = tools.find("jadx")
    assert not status.found
    assert status.state == console.MISSING


def test_found_tool_carries_path_and_version(fake_path):
    fake_path["jadx"] = "/opt/bin/jadx"
    status = tools.find("jadx")
    assert status.found
    assert status.path == "/opt/bin/jadx"
    assert status.version == "1.2.3"
    assert status.state == console.OK


def test_optional_tool_degrades_instead_of_failing(fake_path):
    status = tools.find("ripgrep")
    assert not status.found
    assert status.state == console.WARN
    assert status.spec.fallback  # a documented in-process substitute exists


def test_require_names_every_missing_tool_at_once(fake_path):
    with pytest.raises(tools.MissingToolError) as raised:
        tools.require("java", "jadx")
    assert raised.value.keys == ["java", "jadx"]
    message = str(raised.value)
    assert "jadx" in message and "install:" in message


def test_install_hint_falls_back_to_a_generic_answer():
    hint = tools.spec("jadx").install_hint(system="Haiku")
    assert hint.startswith("https://")


def test_doctor_exits_nonzero_when_a_required_tool_is_missing(fake_path, capsys):
    fake_path["rg"] = "/usr/bin/rg"
    assert main(["doctor"]) == 1
    out, err = capsys.readouterr()
    assert "jadx" in out
    assert "--depth strings" in err  # tells the user what still works


def test_doctor_exits_zero_once_required_tools_are_present(fake_path):
    fake_path.update({"java": "/usr/bin/java", "jadx": "/usr/bin/jadx"})
    assert main(["doctor"]) == 0


def test_doctor_json_output_is_machine_readable(fake_path, capsys):
    fake_path.update({"java": "/usr/bin/java", "jadx": "/usr/bin/jadx"})
    main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    names = {entry["name"] for entry in payload["tools"]}
    assert {"jadx", "java", "rg", "apksigner"} == names
    assert any(c["capability"].startswith("full analysis") for c in payload["capabilities"])
