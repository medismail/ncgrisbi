from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Sequence, Tuple

from .envelope import decode_envelope
from .errors import GsbError, UnsupportedFileVersionError
from .model import ElementSpan, GsbDocument

SUPPORTED_FILE_VERSIONS = ("1.2.1",)
_NAME_RE = re.compile(rb"[A-Za-z_][A-Za-z0-9_.:-]*")
_ATTRIBUTE_RE = re.compile(rb"\s([A-Za-z_][A-Za-z0-9_.:-]*)\s*=")


class LosslessElement(ET.Element):
    """ElementTree node type reserved for compatibility-engine metadata."""


def _find_tag_end(data: bytes, start: int) -> int:
    quote = None
    index = start + 1
    while index < len(data):
        byte = data[index]
        if quote is not None:
            if byte == quote:
                quote = None
        elif byte in (ord('"'), ord("'")):
            quote = byte
        elif byte == ord('>'):
            return index + 1
        index += 1
    raise GsbError("Unterminated XML tag")


def _line_bounds(data: bytes, start: int, end: int) -> Tuple[int, int, bytes]:
    line_start = data.rfind(b"\n", 0, start) + 1
    indent = data[line_start:start]
    if indent.strip():
        line_start = start
        indent = b""

    newline = data.find(b"\n", end)
    line_end = len(data) if newline < 0 else newline + 1
    return line_start, line_end, indent


def _make_span(
    data: bytes,
    tag: str,
    start: int,
    end: int,
    opening_end: int,
) -> ElementSpan:
    line_start, line_end, indent = _line_bounds(data, start, end)
    opening = data[start:opening_end]
    attributes = tuple(
        match.group(1).decode("ascii") for match in _ATTRIBUTE_RE.finditer(opening)
    )
    return ElementSpan(
        tag=tag,
        start=start,
        end=end,
        line_start=line_start,
        line_end=line_end,
        indent=indent,
        attribute_order=attributes,
    )


def scan_top_level_spans(xml_bytes: bytes) -> Tuple[ElementSpan, ...]:
    """Return exact byte spans for direct children of ``<Grisbi>``.

    The scanner is deliberately quote-aware and does not use regular expressions
    to find tag boundaries. This prevents a ``>`` inside an attribute value from
    truncating a record. XML parsing remains the source of semantic truth; this
    scanner supplies only byte locations for surgical writes.
    """
    data = bytes(xml_bytes)
    spans: List[ElementSpan] = []
    depth = 0
    active = None
    index = 0

    while index < len(data):
        start = data.find(b"<", index)
        if start < 0:
            break

        if data.startswith(b"<!--", start):
            close = data.find(b"-->", start + 4)
            if close < 0:
                raise GsbError("Unterminated XML comment")
            index = close + 3
            continue

        if data.startswith(b"<?", start):
            close = data.find(b"?>", start + 2)
            if close < 0:
                raise GsbError("Unterminated XML processing instruction")
            index = close + 2
            continue

        if data.startswith(b"<![CDATA[", start):
            close = data.find(b"]]>", start + 9)
            if close < 0:
                raise GsbError("Unterminated CDATA section")
            index = close + 3
            continue

        end = _find_tag_end(data, start)
        body = data[start + 1:end - 1].strip()
        if not body or body.startswith(b"!"):
            index = end
            continue

        closing = body.startswith(b"/")
        if closing:
            body = body[1:].lstrip()
        match = _NAME_RE.match(body)
        if match is None:
            raise GsbError("Invalid XML tag name")
        tag = match.group(0).decode("ascii")
        self_closing = not closing and body.rstrip().endswith(b"/")

        if closing:
            if depth == 2 and active is not None:
                active_tag, active_start, opening_end = active
                if active_tag != tag:
                    raise GsbError("Mismatched top-level XML element")
                spans.append(_make_span(data, tag, active_start, end, opening_end))
                active = None
            depth -= 1
            if depth < 0:
                raise GsbError("Invalid XML nesting depth")
        else:
            if depth == 1:
                if self_closing:
                    spans.append(_make_span(data, tag, start, end, end))
                else:
                    active = (tag, start, end)
            if not self_closing:
                depth += 1

        index = end

    if depth != 0 or active is not None:
        raise GsbError("Incomplete XML document")
    return tuple(spans)


def _parse_xml(xml_bytes: bytes) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(element_factory=LosslessElement))
    try:
        return ET.fromstring(xml_bytes, parser=parser)
    except ET.ParseError as exc:
        raise GsbError("Invalid GSB XML") from exc


def parse_document(
    raw_bytes: bytes,
    password: Optional[str] = None,
    accepted_file_versions: Sequence[str] = SUPPORTED_FILE_VERSIONS,
) -> GsbDocument:
    decoded = decode_envelope(raw_bytes, password=password)
    root = _parse_xml(decoded.xml_bytes)
    if root.tag != "Grisbi":
        raise GsbError("The XML root element must be Grisbi")

    spans = scan_top_level_spans(decoded.xml_bytes)
    if len(spans) != len(list(root)):
        raise GsbError("Unable to map parsed elements to exact byte spans")

    for element, span in zip(list(root), spans):
        if element.tag != span.tag:
            raise GsbError("Parsed element order differs from byte span order")

    general = root.find("General")
    if general is None:
        raise GsbError("Missing General record")

    file_version = general.get("File_version", "")
    grisbi_version = general.get("Grisbi_version", "")
    if accepted_file_versions and file_version not in accepted_file_versions:
        raise UnsupportedFileVersionError(
            "Unsupported GSB file version: %s" % (file_version or "missing")
        )

    return GsbDocument(
        raw_bytes=bytes(raw_bytes),
        xml_bytes=decoded.xml_bytes,
        envelope=decoded.state,
        root=root,
        spans=spans,
        file_version=file_version,
        grisbi_version=grisbi_version,
    )
