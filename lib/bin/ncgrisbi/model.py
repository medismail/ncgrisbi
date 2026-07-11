from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple

from .envelope import EnvelopeState


@dataclass(frozen=True)
class ElementSpan:
    tag: str
    start: int
    end: int
    line_start: int
    line_end: int
    indent: bytes
    attribute_order: Tuple[str, ...]

    def raw(self, xml_bytes: bytes) -> bytes:
        return xml_bytes[self.start:self.end]


@dataclass(frozen=True)
class GsbDocument:
    raw_bytes: bytes
    xml_bytes: bytes
    envelope: EnvelopeState
    root: ET.Element
    spans: Tuple[ElementSpan, ...]
    file_version: str
    grisbi_version: str

    def spans_for(self, tag: str) -> Tuple[ElementSpan, ...]:
        return tuple(span for span in self.spans if span.tag == tag)

    def find_span(
        self,
        tag: str,
        attribute: str,
        value: str,
    ) -> Optional[ElementSpan]:
        elements = self.root.findall(tag)
        spans = self.spans_for(tag)
        for element, span in zip(elements, spans):
            if element.get(attribute) == value:
                return span
        return None

    def element_for_span(self, target: ElementSpan) -> Optional[ET.Element]:
        tag_spans = self.spans_for(target.tag)
        try:
            index = tag_spans.index(target)
        except ValueError:
            return None
        elements = self.root.findall(target.tag)
        if index >= len(elements):
            return None
        return elements[index]

    @property
    def newline(self) -> bytes:
        return b"\r\n" if b"\r\n" in self.xml_bytes else b"\n"
