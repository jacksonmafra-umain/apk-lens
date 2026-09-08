from __future__ import annotations

from pathlib import Path

from apk_lens import strings


def test_printable_runs_are_extracted(tmp_path: Path):
    blob = tmp_path / "classes.dex"
    blob.write_bytes(b"\x00\x01api.example.com\x00\xff\xfeLcom/example/Thing;\x00")
    found = strings.collect([blob])
    assert "api.example.com" in found
    assert "Lcom/example/Thing;" in found


def test_short_runs_are_ignored(tmp_path: Path):
    blob = tmp_path / "classes.dex"
    blob.write_bytes(b"\x00ab\x00cde\x00longenough\x00")
    assert strings.collect([blob]) == ["longenough"]


def test_a_run_spanning_a_read_boundary_is_not_split(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(strings, "READ_CHUNK_BYTES", 8)
    blob = tmp_path / "classes.dex"
    blob.write_bytes(b"\x00" + b"telemetry.example.com" + b"\x00")
    assert "telemetry.example.com" in strings.collect([blob])


def test_results_are_deduplicated_and_sorted(tmp_path: Path):
    first = tmp_path / "a.dex"
    second = tmp_path / "b.dex"
    first.write_bytes(b"zzzzzz\x00aaaaaa\x00")
    second.write_bytes(b"aaaaaa\x00")
    assert strings.collect([first, second]) == ["aaaaaa", "zzzzzz"]


def test_native_libraries_use_a_higher_floor(tmp_path: Path):
    blob = tmp_path / "libdemo.so"
    blob.write_bytes(b"\x7fELF\x00sevench\x00eightchars\x00")
    found = strings.collect([blob], strings.NATIVE_MIN_LENGTH)
    assert "eightchars" in found
    assert "sevench" not in found


def test_dump_writes_a_file_and_returns_the_count(tmp_path: Path):
    blob = tmp_path / "classes.dex"
    blob.write_bytes(b"api.example.com\x00cdn.example.com\x00")
    target = tmp_path / "out" / "dex-strings.txt"
    assert strings.dump([blob], target) == 2
    assert target.read_text().splitlines() == ["api.example.com", "cdn.example.com"]


def test_an_unreadable_file_is_skipped_rather_than_fatal(tmp_path: Path):
    assert strings.collect([tmp_path / "missing.dex"]) == []
