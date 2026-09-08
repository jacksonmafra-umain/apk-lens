"""A minimal binary-XML *encoder*, used only by the tests.

The decoder in ``apk_lens.axml`` is worth testing against real compiled bytes
rather than against text, and a repository like this one cannot ship a real
APK. So the fixtures compile their own manifests: same chunk layout Android
uses, just the subset the manifest needs (string pool, elements, attributes).
"""

from __future__ import annotations

import struct

ANDROID_NS = "http://schemas.android.com/apk/res/android"

STRING = "string"
INT = "int"
BOOL = "bool"

NO_INDEX = 0xFFFFFFFF


class Attr:
    def __init__(self, name: str, value, kind: str = STRING, android: bool = True) -> None:
        self.name = name
        self.value = value
        self.kind = kind
        self.android = android


class Node:
    def __init__(self, tag: str, attrs: list[Attr] | None = None, children=None) -> None:
        self.tag = tag
        self.attrs = attrs or []
        self.children = children or []


def _pool_strings(node: Node, seen: list[str]) -> None:
    def add(value: str) -> None:
        if value not in seen:
            seen.append(value)

    add(ANDROID_NS)
    add(node.tag)
    for attr in node.attrs:
        add(attr.name)
        if attr.kind == STRING:
            add(str(attr.value))
    for child in node.children:
        _pool_strings(child, seen)


def _encode_pool(strings: list[str]) -> bytes:
    blob = bytearray()
    offsets = []
    for value in strings:
        offsets.append(len(blob))
        encoded = value.encode("utf-16-le")
        blob += struct.pack("<H", len(value)) + encoded + b"\x00\x00"
    while len(blob) % 4:
        blob += b"\x00"

    strings_start = 28 + 4 * len(strings)
    size = strings_start + len(blob)
    header = struct.pack(
        "<HHIIIIII", 0x0001, 28, size, len(strings), 0, 0, strings_start, 0
    )
    return header + b"".join(struct.pack("<I", offset) for offset in offsets) + bytes(blob)


def _encode_attr(attr: Attr, index) -> bytes:
    ns = index(ANDROID_NS) if attr.android else NO_INDEX
    name = index(attr.name)
    if attr.kind == STRING:
        raw = index(str(attr.value))
        data_type, data = 0x03, raw
    elif attr.kind == BOOL:
        raw, data_type, data = NO_INDEX, 0x12, 1 if attr.value else 0
    else:
        raw, data_type, data = NO_INDEX, 0x10, int(attr.value) & 0xFFFFFFFF
    return struct.pack("<IIIHBBI", ns, name, raw, 8, 0, data_type, data)


def _encode_node(node: Node, index) -> bytes:
    attributes = b"".join(_encode_attr(attr, index) for attr in node.attrs)
    # Written field by field: the node header, then the attribute extension,
    # so the layout stays readable against ResourceTypes.h.
    start = (
        struct.pack("<HHI", 0x0102, 16, 36 + len(attributes))
        + struct.pack("<II", 0, NO_INDEX)
        + struct.pack("<II", NO_INDEX, index(node.tag))
        + struct.pack("<HHHHHH", 20, 20, len(node.attrs), 0, 0, 0)
    )
    body = start + attributes
    for child in node.children:
        body += _encode_node(child, index)
    end = struct.pack("<HHIIIII", 0x0103, 16, 24, 0, NO_INDEX, NO_INDEX, index(node.tag))
    return body + end


def encode(root: Node) -> bytes:
    strings: list[str] = []
    _pool_strings(root, strings)
    lookup = {value: position for position, value in enumerate(strings)}

    pool = _encode_pool(strings)
    body = _encode_node(root, lookup.__getitem__)
    total = 8 + len(pool) + len(body)
    return struct.pack("<HHI", 0x0003, 8, total) + pool + body
