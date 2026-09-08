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


# --------------------------------------------------------------------------
# Mirror pages: the ranking is a safety property, not a convenience. An app
# page carries adverts for *other* apps, and those adverts are often
# better-formed file links than the real target.
# --------------------------------------------------------------------------

APP_PAGE = """
<html><body>
  <a href="https://download.mirror.test">Downloads</a>
  <a id="download_btn" href="/login">Sign in to download</a>
  <a href="/other/com.other.app/download?refapk=com.example.demo">Try this app too</a>
  <a href="/demo/com.example.demo/download">Download</a>
</body></html>
"""

DOWNLOAD_PAGE = """
<html><body>
  <a href="/custom/com.other.app-3207837.apk?token=1">Get the mirror app</a>
  <a id="download_link" class="ga" href="{direct}" rel="nofollow">Download APK</a>
</body></html>
"""


def _serve_mirror(root: Path, payload: bytes, direct_path: str = "/b/XAPK/com.example.demo"):
    # `download/index.html`, so the fixture server serves it as text/html the
    # way a mirror's download page is served.
    (root / "demo" / "com.example.demo" / "download").mkdir(parents=True)
    (root / "demo" / "com.example.demo" / "download" / "index.html").write_text(
        DOWNLOAD_PAGE.format(direct=direct_path)
    )
    (root / "b" / "XAPK").mkdir(parents=True)
    (root / "b" / "XAPK" / "com.example.demo").write_bytes(payload)
    (root / "custom").mkdir()
    (root / "custom" / "com.other.app-3207837.apk").write_bytes(b"WRONG APP")
    (root / "app.html").write_text(APP_PAGE)


def test_a_two_hop_mirror_page_resolves_to_the_right_file(
    http_root, xapk_file: Path, tmp_path: Path
):
    root, base_url = http_root
    _serve_mirror(root, xapk_file.read_bytes())

    record = acquire.acquire(f"{base_url}/app.html", tmp_path / "apks")

    # Not the advert, and not the sign-in page.
    assert record.resolved_url.endswith("/b/XAPK/com.example.demo")
    assert record.container == "xapk"


def test_an_advert_for_another_app_is_never_the_download(tmp_path: Path):
    """The failure this guards against produces a confident report about the
    wrong software, which is worse than producing none."""
    wanted = acquire.package_ids_in("https://mirror.test/demo/com.example.demo")
    candidates = acquire._page_links(
        DOWNLOAD_PAGE.format(direct="/b/XAPK/com.example.demo"),
        "https://mirror.test/demo/com.example.demo/download",
        wanted=wanted,
    )
    assert candidates == ["https://mirror.test/b/XAPK/com.example.demo"]
    assert not any("com.other.app" in candidate for candidate in candidates)


def test_a_referrer_parameter_cannot_launder_a_foreign_package():
    """Mirrors pass the referring app along in the query, so "mentions the
    wanted package" is not enough — it must not mention any other."""
    wanted = {"com.example.demo"}
    candidates = acquire._page_links(APP_PAGE, "https://mirror.test/demo", wanted=wanted)
    assert all("com.other.app" not in candidate for candidate in candidates)
    assert "https://mirror.test/demo/com.example.demo/download" in candidates


def test_an_extension_less_download_link_is_recognised():
    """The real button is often `d.<mirror>/b/XAPK/<package>` — no extension."""
    html = '<a id="download_link" href="https://d.mirror.test/b/XAPK/com.example.demo?v=1">go</a>'
    assert acquire._page_links(html, "https://mirror.test/x", wanted={"com.example.demo"}) == [
        "https://d.mirror.test/b/XAPK/com.example.demo?v=1"
    ]


def test_a_bare_host_is_not_a_candidate():
    html = '<a href="https://download.mirror.test">Downloads</a>'
    assert acquire._page_links(html, "https://mirror.test/x") == []


def test_a_sign_in_button_named_download_is_not_followed():
    html = '<a id="download_btn" href="/login">Sign in to download</a>'
    assert acquire._page_links(html, "https://mirror.test/x", wanted={"com.example.demo"}) == []


def test_html_escaped_links_are_unescaped():
    html = '<a href="https://d.mirror.test/f.xapk?a=1&amp;b=2">x</a>'
    assert acquire._page_links(html, "https://mirror.test/x") == [
        "https://d.mirror.test/f.xapk?a=1&b=2"
    ]


def test_a_page_offering_only_another_app_fails_rather_than_downloading_it(
    http_root, tmp_path: Path
):
    root, base_url = http_root
    (root / "custom").mkdir()
    (root / "custom" / "com.other.app-1.apk").write_bytes(b"WRONG APP")
    (root / "only-adverts.html").write_text(
        '<html><a href="/custom/com.other.app-1.apk">Download</a></html>'
    )

    with pytest.raises(AcquisitionError, match="no download link for this app"):
        acquire.acquire(f"{base_url}/only-adverts.html?pkg=com.example.demo", tmp_path / "apks")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://apkpure.example/accessy/com.axessions.app", {"com.axessions.app"}),
        ("https://d.host.example/b/XAPK/com.axessions.app?version=latest", {"com.axessions.app"}),
        ("https://d.host.example/custom/com.apkpure.aegon-320.apk", {"com.apkpure.aegon"}),
        ("https://download.host.example", set()),
        ("SomeApp_1.0.xapk", set()),
    ],
)
def test_package_ids_are_read_from_the_path_not_the_hostname(url, expected):
    assert acquire.package_ids_in(url) == expected


def test_the_wanted_app_is_inferred_when_the_url_does_not_name_it():
    """A pasted URL does not always carry the package (`/accessy/download`),
    and without an anchor the advert filter has nothing to compare against."""
    assert acquire.infer_wanted(APP_PAGE) == {"com.example.demo"}


def test_an_ambiguous_page_infers_nothing_rather_than_guessing():
    html = (
        '<a href="/a/com.one.app/download">a</a>'
        '<a href="/b/com.two.app/download">b</a>'
    )
    assert acquire.infer_wanted(html) == set()
