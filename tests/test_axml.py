from __future__ import annotations

import pytest

from apk_lens import axml
from apk_lens.axml import MalformedAxmlError
from axml_builder import BOOL, INT, Attr, Node, encode


def test_binary_manifest_round_trips_through_the_decoder():
    blob = encode(
        Node(
            "manifest",
            [Attr("package", "com.example.demo", android=False), Attr("versionCode", 42, INT)],
            [Node("uses-permission", [Attr("name", "android.permission.INTERNET")])],
        )
    )
    root = axml.parse_bytes(blob)
    assert root.tag == "manifest"
    assert root.get("package") == "com.example.demo"
    assert root.get("versionCode") == "42"
    assert root.findall("uses-permission")[0].get("android:name").endswith("INTERNET")


def test_namespaced_attributes_are_reachable_both_ways():
    root = axml.parse_bytes(encode(Node("manifest", [Attr("versionName", "9.9")])))
    assert root.get("versionName") == root.get("android:versionName") == "9.9"


def test_booleans_decode_as_words_not_numbers():
    root = axml.parse_bytes(
        encode(
            Node(
                "application",
                [Attr("debuggable", True, BOOL), Attr("allowBackup", False, BOOL)],
            )
        )
    )
    assert root.get("debuggable") == "true"
    assert root.get("allowBackup") == "false"


def test_nesting_is_preserved():
    root = axml.parse_bytes(
        encode(
            Node(
                "manifest",
                [],
                [Node("application", [], [Node("activity", [Attr("name", ".Main")])])],
            )
        )
    )
    tags = [element.tag for element in root.iter()]
    assert tags == ["manifest", "application", "activity"]


def test_plain_text_manifests_are_accepted_too():
    text = (
        b'<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
        b'package="com.example.demo">'
        b'<uses-permission android:name="android.permission.CAMERA"/>'
        b"</manifest>"
    )
    root = axml.parse_bytes(text)
    assert root.get("package") == "com.example.demo"
    assert root.findall("uses-permission")[0].get("android:name").endswith("CAMERA")


def test_an_empty_file_is_reported_rather_than_crashing():
    with pytest.raises(MalformedAxmlError, match="empty"):
        axml.parse_bytes(b"")


def test_a_non_manifest_binary_is_reported():
    with pytest.raises(MalformedAxmlError, match="unexpected chunk type"):
        axml.parse_bytes(b"\x99\x99\x08\x00rubbish")
