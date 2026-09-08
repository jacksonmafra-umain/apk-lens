from __future__ import annotations

import zlib
from pathlib import Path

from apk_lens import obfuscation

CONFIG = b'{"endpoint":"https://cfg.example.com/v1","retries":3}'


def test_single_byte_xor_is_recovered_with_its_key(tmp_path: Path):
    asset = tmp_path / "builtin_config"
    asset.write_bytes(bytes(byte ^ 0x55 for byte in CONFIG))

    decoded = obfuscation.candidates(asset)
    assert len(decoded) == 1
    assert decoded[0].transform == "single-byte XOR"
    assert decoded[0].key == "0x55"
    assert "cfg.example.com" in decoded[0].preview


def test_the_best_key_wins_rather_than_the_first_plausible_one(tmp_path: Path):
    """Stopping at the first key that looks printable produces confident nonsense."""
    asset = tmp_path / "config.bin"
    asset.write_bytes(bytes(byte ^ 0x2A for byte in CONFIG))
    assert obfuscation.candidates(asset)[0].key == "0x2a"


def test_every_result_can_be_reproduced_by_hand(tmp_path: Path):
    asset = tmp_path / "config.bin"
    asset.write_bytes(bytes(byte ^ 0x11 for byte in CONFIG))
    assert "0x11" in obfuscation.candidates(asset)[0].reproduce


def test_compressed_assets_are_decompressed(tmp_path: Path):
    asset = tmp_path / "packed.bin"
    asset.write_bytes(zlib.compress(CONFIG))
    decoded = obfuscation.candidates(asset)
    assert decoded[0].transform == "zlib"
    assert "cfg.example.com" in decoded[0].preview


def test_plain_text_is_reported_as_untransformed(tmp_path: Path):
    asset = tmp_path / "endpoints.json"
    asset.write_bytes(CONFIG)
    decoded = obfuscation.candidates(asset)
    assert decoded[0].transform == "none"


def test_random_bytes_produce_nothing(tmp_path: Path):
    asset = tmp_path / "noise.bin"
    asset.write_bytes(bytes(range(256)) * 8)
    assert obfuscation.candidates(asset) == []


def test_an_image_is_not_mistaken_for_configuration(tmp_path: Path):
    asset = tmp_path / "icon.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4)
    assert obfuscation.candidates(asset) == []


def test_oversized_assets_are_skipped(tmp_path: Path, monkeypatch):
    from apk_lens import catalog

    asset = tmp_path / "big.bin"
    asset.write_bytes(CONFIG)
    monkeypatch.setitem(
        catalog.load("native")["asset_decoding"], "max_asset_bytes", 4
    )
    assert obfuscation.candidates(asset) == []


def test_a_missing_file_is_not_fatal(tmp_path: Path):
    assert obfuscation.candidates(tmp_path / "absent.bin") == []
