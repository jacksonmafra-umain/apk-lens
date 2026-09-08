from __future__ import annotations

import json
from pathlib import Path

from apk_lens import axml, manifest
from apk_lens.cli import main
from axml_builder import BOOL, INT, Attr, Node, encode
from conftest import manifest_bytes


def facts_from_nodes(root: Node):
    return manifest.facts_from(axml.parse_bytes(encode(root)))


def test_core_identity_is_extracted():
    facts = manifest.facts_from(axml.parse_bytes(manifest_bytes()))
    assert facts.package == "com.example.demo"
    assert facts.version_name == "1.0"
    assert facts.version_code == "100"
    assert facts.min_sdk == "24"
    assert facts.target_sdk == "34"


def test_permissions_are_deduplicated_and_sorted():
    facts = facts_from_nodes(
        Node(
            "manifest",
            [],
            [
                Node("uses-permission", [Attr("name", "android.permission.CAMERA")]),
                Node("uses-permission", [Attr("name", "android.permission.CAMERA")]),
                Node("uses-permission", [Attr("name", "android.permission.INTERNET")]),
            ],
        )
    )
    assert facts.permissions == [
        "android.permission.CAMERA",
        "android.permission.INTERNET",
    ]


def test_custom_permissions_are_kept_apart_from_requested_ones():
    facts = manifest.facts_from(axml.parse_bytes(manifest_bytes()))
    assert facts.declared_permissions == ["com.example.demo.permission.CUSTOM"]
    assert "com.example.demo.permission.CUSTOM" not in facts.permissions


def test_queried_packages_are_collected():
    facts = manifest.facts_from(axml.parse_bytes(manifest_bytes()))
    assert facts.queried_packages == ["com.example.other", "com.example.rival"]


def test_network_and_backup_posture_is_read():
    facts = manifest.facts_from(axml.parse_bytes(manifest_bytes()))
    assert facts.uses_cleartext_traffic is True
    assert facts.allow_backup is True
    assert facts.debuggable is None  # not declared, and not assumed


def test_declared_export_is_reported_with_its_source():
    facts = manifest.facts_from(axml.parse_bytes(manifest_bytes()))
    activity = next(c for c in facts.components if c.name == ".MainActivity")
    assert activity.exported is True
    assert activity.exported_source == "declared in the manifest"


def test_an_intent_filter_exports_a_component_on_older_target_sdks():
    facts = facts_from_nodes(
        Node(
            "manifest",
            [],
            [
                Node("uses-sdk", [Attr("targetSdkVersion", 29, INT)]),
                Node(
                    "application",
                    [],
                    [
                        Node(
                            "activity",
                            [Attr("name", ".Legacy")],
                            [Node("intent-filter", [], [Node("action", [Attr("name", "VIEW")])])],
                        )
                    ],
                ),
            ],
        )
    )
    activity = facts.components[0]
    assert activity.exported is True
    assert "intent filter" in activity.exported_source
    assert activity.actions == ("VIEW",)


def test_an_undeclared_export_on_modern_sdks_is_left_undecided():
    facts = facts_from_nodes(
        Node(
            "manifest",
            [],
            [
                Node("uses-sdk", [Attr("targetSdkVersion", 34, INT)]),
                Node(
                    "application",
                    [],
                    [
                        Node(
                            "receiver",
                            [Attr("name", ".Boot")],
                            [Node("intent-filter", [], [Node("action", [Attr("name", "BOOT")])])],
                        )
                    ],
                ),
            ],
        )
    )
    # Not guessed either way: on SDK 31+ this manifest would not install.
    assert facts.components[0].exported is None


def test_providers_default_to_private_on_modern_sdks():
    facts = facts_from_nodes(
        Node(
            "manifest",
            [],
            [
                Node("uses-sdk", [Attr("targetSdkVersion", 34, INT)]),
                Node(
                    "application",
                    [],
                    [Node("provider", [Attr("name", ".P"), Attr("authorities", "a.b")])],
                ),
            ],
        )
    )
    assert facts.components[0].exported is False
    assert "SDK 17+" in facts.components[0].exported_source


def test_a_permission_guard_stops_a_component_being_openly_exported():
    facts = facts_from_nodes(
        Node(
            "manifest",
            [],
            [
                Node(
                    "application",
                    [],
                    [
                        Node(
                            "service",
                            [
                                Attr("name", ".Guarded"),
                                Attr("exported", True, BOOL),
                                Attr("permission", "com.example.demo.permission.CUSTOM"),
                            ],
                        )
                    ],
                )
            ],
        )
    )
    component = facts.components[0]
    assert component.exported is True
    assert component.guarded
    assert not component.openly_exported
    assert facts.openly_exported_components == []


def test_manifest_command_emits_json(apk_file: Path, tmp_path: Path, capsys):
    exit_code = main(
        [
            "manifest",
            str(apk_file),
            "--work-dir",
            str(tmp_path / "work"),
            "--apks-dir",
            str(tmp_path / "apks"),
            "--category",
            "social",
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["manifest"]["package"] == "com.example.demo"
    assert payload["permissions"]["category"] == "social"
