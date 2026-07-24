from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple
from xml.sax.saxutils import escape

from .envelope import encode_envelope
from .errors import GsbError, PatchConflictError
from .formats import FormatProfile
from .model import ElementSpan, GsbDocument


@dataclass(frozen=True)
class Patch:
    start: int
    end: int
    replacement: bytes
    description: str
    sequence: int


class LosslessPatchWriter:
    def __init__(
        self,
        document: GsbDocument,
        profile: Optional[FormatProfile] = None,
    ):
        self.document = document
        self.profile = profile or document.format_profile
        if self.profile.file_version != document.file_version:
            raise GsbError(
                "Writer profile %s does not match document format %s"
                % (self.profile.file_version, document.file_version)
            )
        self._patches: List[Patch] = []
        self._sequence = 0

    @property
    def changed(self) -> bool:
        return bool(self._patches)

    def _append(self, start: int, end: int, replacement: bytes, description: str) -> None:
        if start < 0 or end < start or end > len(self.document.xml_bytes):
            raise PatchConflictError("Patch range is outside the XML document")
        self._patches.append(
            Patch(start, end, bytes(replacement), description, self._sequence)
        )
        self._sequence += 1

    @staticmethod
    def _validate_fragment(expected_tag: str, replacement: bytes) -> None:
        try:
            element = ET.fromstring(replacement)
        except ET.ParseError as exc:
            raise GsbError("Replacement is not a valid XML element") from exc
        if element.tag != expected_tag:
            raise GsbError(
                "Replacement tag %s does not match %s" % (element.tag, expected_tag)
            )

    def replace(self, span: ElementSpan, replacement: bytes) -> None:
        self._validate_fragment(span.tag, replacement)
        self._append(span.start, span.end, replacement, "replace %s" % span.tag)

    def replace_record(self, span: ElementSpan, attributes: Mapping) -> None:
        self.replace(span, self.profile.serialize_record(span.tag, attributes))

    def replace_attribute(
        self,
        span: ElementSpan,
        attribute: str,
        value: object,
    ) -> None:
        """Patch one attribute value without serializing the surrounding record.

        A batch of checked/unchecked rows changes only the ``Ma`` values and
        preserves every other byte, including attribute order, quoting,
        whitespace and metadata unknown to NCGrisbi.
        """
        raw = span.raw(self.document.xml_bytes)
        pattern = re.compile(
            rb"(?P<prefix>\s"
            + re.escape(attribute.encode("ascii"))
            + rb"\s*=\s*)(?P<quote>[\"'])(?P<value>[\s\S]*?)(?P=quote)"
        )
        match = pattern.search(raw)
        if match is None:
            raise GsbError("%s attribute %s is missing" % (span.tag, attribute))
        encoded = escape(
            str(value),
            {
                '"': "&quot;",
                "\r": "&#13;",
                "\n": "&#10;",
                "\t": "&#9;",
            },
        ).encode("utf-8")
        start = span.start + match.start("value")
        end = span.start + match.end("value")
        self._append(
            start,
            end,
            encoded,
            "replace %s.%s" % (span.tag, attribute),
        )

    def delete(self, span: ElementSpan) -> None:
        # Delete the entire physical line only when it contains the record and
        # indentation. Multiline or inline elements fall back to the exact span.
        prefix = self.document.xml_bytes[span.line_start:span.start]
        suffix = self.document.xml_bytes[span.end:span.line_end]
        if not prefix.strip() and not suffix.strip():
            self._append(span.line_start, span.line_end, b"", "delete %s" % span.tag)
        else:
            self._append(span.start, span.end, b"", "delete %s" % span.tag)

    def _root_close_line_start(self) -> int:
        close = self.document.xml_bytes.rfind(b"</Grisbi>")
        if close < 0:
            raise GsbError("Missing Grisbi closing tag")
        return self.document.xml_bytes.rfind(b"\n", 0, close) + 1

    def _insertion_point(
        self,
        tag: str,
        after: Optional[ElementSpan],
    ) -> Tuple[int, bytes]:
        if after is not None:
            if after not in self.document.spans:
                raise GsbError("Insertion anchor does not belong to this document")
            return after.line_end, after.indent or b"\t"

        section_rank = self.profile.section_rank
        if tag not in section_rank:
            raise GsbError(
                "Unknown Grisbi %s section for insertion: %s"
                % (self.profile.file_version, tag)
            )
        rank = section_rank[tag]

        same_group = [
            span for span in self.document.spans
            if section_rank.get(span.tag) == rank
        ]
        if same_group:
            anchor = same_group[-1]
            return anchor.line_end, anchor.indent or b"\t"

        later = [
            span for span in self.document.spans
            if section_rank.get(span.tag, 10 ** 6) > rank
        ]
        if later:
            anchor = later[0]
            return anchor.line_start, anchor.indent or b"\t"

        return self._root_close_line_start(), b"\t"

    def insert_record(
        self,
        tag: str,
        attributes: Mapping,
        after: Optional[ElementSpan] = None,
    ) -> None:
        position, indent = self._insertion_point(tag, after)
        record = self.profile.serialize_record(tag, attributes)
        replacement = indent + record + self.document.newline
        self._append(position, position, replacement, "insert %s" % tag)

    def _ordered_patches(self) -> List[Patch]:
        patches = sorted(
            self._patches,
            key=lambda patch: (patch.start, patch.sequence),
            reverse=True,
        )

        occupied_start = len(self.document.xml_bytes) + 1
        for patch in patches:
            # Multiple zero-length insertions at one position are allowed. Every
            # other overlap is a conflict because patch ordering would be unclear.
            if patch.start == patch.end and patch.start == occupied_start:
                continue
            if patch.end > occupied_start:
                raise PatchConflictError("Byte patches overlap")
            occupied_start = patch.start
        return patches

    def render_xml(self) -> bytes:
        if not self._patches:
            return self.document.xml_bytes

        result = self.document.xml_bytes
        for patch in self._ordered_patches():
            result = result[:patch.start] + patch.replacement + result[patch.end:]
        try:
            root = ET.fromstring(result)
        except ET.ParseError as exc:
            raise GsbError("Patched output is not valid XML") from exc
        if root.tag != "Grisbi":
            raise GsbError("Patched output no longer has a Grisbi root")
        general = root.find("General")
        if general is None or general.get("File_version") != self.document.file_version:
            raise GsbError("Patched output changed the GSB file version")
        return result

    def render(self, password: Optional[str] = None) -> bytes:
        # This is the central no-op guarantee: do not parse/re-serialize, decrypt,
        # recompress or re-encrypt when no mutation was requested.
        if not self._patches:
            return self.document.raw_bytes
        return encode_envelope(
            self.render_xml(),
            self.document.envelope,
            password=password,
        )
