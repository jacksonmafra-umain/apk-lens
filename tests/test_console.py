from __future__ import annotations

from apk_lens import console


def test_table_columns_align_on_the_widest_cell(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    rendered = console.render_table(
        ("tool", "state"), [("jadx", "ok"), ("apksigner", "missing")]
    )
    lines = rendered.splitlines()
    assert lines[0] == "tool       state"
    assert lines[2] == "jadx       ok"
    assert lines[3] == "apksigner  missing"


def test_style_is_a_no_op_without_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert console.style("plain", "bold") == "plain"
