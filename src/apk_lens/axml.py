"""A decoder for Android's binary XML (AXML).

`AndroidManifest.xml` inside an APK is not text. It is Android's compiled
resource format: a string pool followed by a stream of element chunks. Decoding
it is the cheapest high-signal step in the whole analysis — the manifest says
what an app asks for, what it exposes to other apps, and what it is allowed to
see about the rest of the device, and it needs no decompiler at all.

Only the manifest subset is implemented: string pool, namespaces, elements and
attributes. Styles, and resource references beyond their numeric id, are not
resolved — a reference is reported as ``@0x7f0a0001`` so a reader can tell
"this is a resource" from "this is a literal".

Reference: ``ResourceTypes.h`` in the Android platform sources.
"""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path

from apk_lens.errors import ApkLensError

CHUNK_STRING_POOL = 0x0001
CHUNK_XML = 0x0003
CHUNK_XML_START_NAMESPACE = 0x0100
CHUNK_XML_END_NAMESPACE = 0x0101
CHUNK_XML_START_ELEMENT = 0x0102
CHUNK_XML_END_ELEMENT = 0x0103
CHUNK_XML_CDATA = 0x0104
CHUNK_XML_RESOURCE_MAP = 0x0180

FLAG_UTF8 = 1 << 8

TYPE_REFERENCE = 0x01
TYPE_ATTRIBUTE = 0x02
TYPE_STRING = 0x03
TYPE_FLOAT = 0x04
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12

ANDROID_NS = "http://schemas.android.com/apk/res/android"


class MalformedAxmlError(ApkLensError):
    """The file is not decodable binary XML."""


@dataclass
class Element:
    """One XML element, with attributes keyed by their local name."""

    tag: str
    attributes: dict[str, str] = field(default_factory=dict)
    children: list[Element] = field(default_factory=list)

    def get(self, name: str, default: str | None = None) -> str | None:
        return self.attributes.get(name, default)

    def findall(self, tag: str) -> list[Element]:
        return [child for child in self.children if child.tag == tag]

    def iter(self):
        yield self
        for child in self.children:
            yield from child.iter()


class _StringPool:
    def __init__(self, data: bytes) -> None:
        count, _styles, flags, strings_start, _styles_start = struct.unpack_from("<IIIII", data, 8)
        self._utf8 = bool(flags & FLAG_UTF8)
        self._data = data
        self._offsets = struct.unpack_from(f"<{count}I", data, 28)
        self._strings_start = strings_start
        self._cache: dict[int, str] = {}

    def __len__(self) -> int:
        return len(self._offsets)

    def get(self, index: int) -> str:
        if index < 0 or index >= len(self._offsets):
            return ""
        if index in self._cache:
            return self._cache[index]

        at = self._strings_start + self._offsets[index]
        value = self._read_utf8(at) if self._utf8 else self._read_utf16(at)
        self._cache[index] = value
        return value

    def _read_utf8(self, at: int) -> str:
        # Two length fields (characters, then bytes), each 1 or 2 bytes.
        at = self._skip_varint(at)
        at, byte_length = self._varint(at)
        return self._data[at : at + byte_length].decode("utf-8", "replace")

    def _read_utf16(self, at: int) -> str:
        length = struct.unpack_from("<H", self._data, at)[0]
        at += 2
        if length & 0x8000:  # long string: a second 16-bit word
            length = ((length & 0x7FFF) << 16) | struct.unpack_from("<H", self._data, at)[0]
            at += 2
        return self._data[at : at + length * 2].decode("utf-16-le", "replace")

    def _varint(self, at: int) -> tuple[int, int]:
        first = self._data[at]
        if first & 0x80:
            return at + 2, ((first & 0x7F) << 8) | self._data[at + 1]
        return at + 1, first

    def _skip_varint(self, at: int) -> int:
        return self._varint(at)[0]


def _format_value(pool: _StringPool, raw_index: int, data_type: int, data: int) -> str:
    if data_type == TYPE_STRING:
        return pool.get(data)
    if data_type == TYPE_INT_BOOLEAN:
        return "true" if data else "false"
    if data_type == TYPE_REFERENCE:
        return f"@0x{data:08x}"
    if data_type == TYPE_ATTRIBUTE:
        return f"?0x{data:08x}"
    if data_type == TYPE_INT_HEX:
        return f"0x{data:x}"
    if data_type == TYPE_FLOAT:
        return str(struct.unpack("<f", struct.pack("<I", data))[0])
    if data_type >= TYPE_INT_DEC:
        # Manifest integers are signed (minSdkVersion, versionCode).
        return str(data - (1 << 32) if data >= (1 << 31) else data)
    if raw_index != 0xFFFFFFFF:
        return pool.get(raw_index)
    return str(data)


def parse_bytes(payload: bytes) -> Element:
    """Decode binary XML, or plain-text XML, into an :class:`Element` tree."""
    if not payload:
        raise MalformedAxmlError("the manifest is empty")

    if payload.lstrip()[:1] in (b"<", b"\xef"):
        return _from_text(payload)

    chunk_type = struct.unpack_from("<H", payload, 0)[0]
    if chunk_type != CHUNK_XML:
        raise MalformedAxmlError(
            f"unexpected chunk type 0x{chunk_type:04x} at the start of the manifest"
        )

    pool: _StringPool | None = None
    root: Element | None = None
    stack: list[Element] = []
    at = struct.unpack_from("<H", payload, 2)[0]  # skip the file header
    limit = len(payload)

    while at + 8 <= limit:
        kind, header_size, size = struct.unpack_from("<HHI", payload, at)
        if size < 8 or at + size > limit:
            break
        body = payload[at : at + size]

        if kind == CHUNK_STRING_POOL:
            pool = _StringPool(body)
        elif kind == CHUNK_XML_START_ELEMENT:
            if pool is None:
                raise MalformedAxmlError("an element appeared before the string pool")
            element = _read_element(body, header_size, pool)
            if stack:
                stack[-1].children.append(element)
            else:
                root = root or element
            stack.append(element)
        elif kind == CHUNK_XML_END_ELEMENT:
            if stack:
                stack.pop()
        elif kind in (
            CHUNK_XML_START_NAMESPACE,
            CHUNK_XML_END_NAMESPACE,
            CHUNK_XML_CDATA,
            CHUNK_XML_RESOURCE_MAP,
        ):
            pass  # not needed to read a manifest

        at += size

    if root is None:
        raise MalformedAxmlError("no elements were found in the manifest")
    return root


def _read_element(body: bytes, header_size: int, pool: _StringPool) -> Element:
    name_index = struct.unpack_from("<I", body, header_size + 4)[0]
    attribute_start, attribute_size, attribute_count = struct.unpack_from(
        "<HHH", body, header_size + 8
    )

    element = Element(tag=pool.get(name_index))
    for index in range(attribute_count):
        at = header_size + attribute_start + index * attribute_size
        if at + 20 > len(body):
            break
        ns_index, attr_name, raw_value = struct.unpack_from("<III", body, at)
        data_type, data = struct.unpack_from("<BI", body, at + 15)

        local_name = pool.get(attr_name)
        if not local_name:
            continue
        value = _format_value(pool, raw_value, data_type, data)
        element.attributes[local_name] = value
        if pool.get(ns_index) == ANDROID_NS:
            element.attributes.setdefault(f"android:{local_name}", value)
    return element


def _from_text(payload: bytes) -> Element:
    """Accept a plain-text manifest too, so decoded inputs stay usable."""
    try:
        root = ElementTree.fromstring(payload.decode("utf-8", "replace"))
    except ElementTree.ParseError as failure:
        raise MalformedAxmlError(
            f"the manifest is neither binary nor valid XML: {failure}"
        ) from failure

    def convert(node: ElementTree.Element) -> Element:
        element = Element(tag=node.tag.rsplit("}", 1)[-1])
        for key, value in node.attrib.items():
            local = key.rsplit("}", 1)[-1]
            element.attributes[local] = value
            if key.startswith(f"{{{ANDROID_NS}}}"):
                element.attributes[f"android:{local}"] = value
        element.children = [convert(child) for child in node]
        return element

    return convert(root)


def parse_file(path: Path) -> Element:
    try:
        return parse_bytes(path.read_bytes())
    except OSError as failure:
        raise MalformedAxmlError(f"could not read {path}: {failure}") from failure
