from __future__ import annotations

import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from apk_lens import acquire
from apk_lens.cli import main
from apk_lens.errors import AcquisitionError


@pytest.fixture
def http_root(tmp_path: Path):
    """A throwaway local web server. The suite never touches the network."""
    root = tmp_path / "www"
    root.mkdir()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *args):  # keep pytest output clean
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_local_file_is_recorded_without_being_moved(apk_file: Path):
    record = acquire.acquire(str(apk_file))
    assert record.kind == acquire.LOCAL
    assert Path(record.path) == apk_file.resolve()
    assert apk_file.exists()
    assert len(record.sha256) == 64
    assert acquire.provenance_path(apk_file).exists()


def test_provenance_round_trips_through_json(apk_file: Path):
    written = acquire.acquire(str(apk_file))
    assert acquire.read_provenance(apk_file) == written


def test_download_stores_the_file_and_its_provenance(http_root, xapk_file: Path, tmp_path: Path):
    root, base_url = http_root
    (root / "demo.xapk").write_bytes(xapk_file.read_bytes())

    dest = tmp_path / "apks"
    record = acquire.acquire(f"{base_url}/demo.xapk", dest)

    assert record.kind == acquire.DOWNLOAD
    assert record.container == "xapk"
    assert (dest / "demo.xapk").exists()
    assert json.loads(acquire.provenance_path(dest / "demo.xapk").read_text())["sha256"]


def test_second_download_reuses_the_cached_file(http_root, apk_file: Path, tmp_path: Path):
    root, base_url = http_root
    (root / "demo.apk").write_bytes(apk_file.read_bytes())
    dest = tmp_path / "apks"

    first = acquire.acquire(f"{base_url}/demo.apk", dest)
    (root / "demo.apk").unlink()  # the mirror goes away; the cache must carry the run
    second = acquire.acquire(f"{base_url}/demo.apk", dest)

    assert second == first


def test_a_download_page_is_followed_to_the_file(http_root, apk_file: Path, tmp_path: Path):
    root, base_url = http_root
    (root / "demo-1.0.apk").write_bytes(apk_file.read_bytes())
    (root / "app.html").write_text(
        '<html><body><a href="/nope">Reviews</a>'
        '<a href="/demo-1.0.apk">Download APK</a></body></html>'
    )

    record = acquire.acquire(f"{base_url}/app.html", tmp_path / "apks")
    assert record.filename == "demo-1.0.apk"
    assert record.resolved_url.endswith("/demo-1.0.apk")
    assert record.source.endswith("/app.html")


def test_a_page_without_any_download_link_explains_what_to_do(http_root, tmp_path: Path):
    root, base_url = http_root
    (root / "empty.html").write_text("<html><body>no links here</body></html>")

    with pytest.raises(AcquisitionError) as raised:
        acquire.acquire(f"{base_url}/empty.html", tmp_path / "apks")
    assert "no download link" in str(raised.value)
    assert "direct file URL" in raised.value.hint


def test_size_limit_is_enforced(http_root, xapk_file: Path, tmp_path: Path):
    root, base_url = http_root
    (root / "big.xapk").write_bytes(xapk_file.read_bytes())

    with pytest.raises(AcquisitionError, match="limit"):
        acquire.acquire(f"{base_url}/big.xapk", tmp_path / "apks", max_bytes=64)


def test_missing_host_is_reported_as_unreachable(tmp_path: Path):
    with pytest.raises(AcquisitionError, match="could not reach"):
        acquire.acquire("http://127.0.0.1:1/demo.apk", tmp_path / "apks")


def test_acquire_command_emits_json(apk_file: Path, capsys):
    assert main(["acquire", str(apk_file), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["container"] == "apk"


def test_acquire_command_reports_a_bad_input_without_a_traceback(tmp_path: Path, capsys):
    junk = tmp_path / "notes.txt"
    junk.write_text("hello")
    assert main(["acquire", str(junk)]) == 2
    assert "not a ZIP-based Android bundle" in capsys.readouterr().err


def test_human_size_reads_naturally():
    assert acquire.human_size(512) == "512 B"
    assert acquire.human_size(195 * 1024 * 1024) == "195.0 MB"
