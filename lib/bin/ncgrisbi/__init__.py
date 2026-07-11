"""Lossless Grisbi 1.2.2 / GSB 1.2.1 compatibility primitives."""

from .envelope import (
    DecodedEnvelope,
    EnvelopeState,
    decode_envelope,
    encode_envelope,
    inspect_envelope,
)
from .errors import (
    EnvelopeError,
    GsbError,
    PasswordRequiredError,
    PatchConflictError,
    UnsupportedFileVersionError,
)
from .model import ElementSpan, GsbDocument
from .parser import parse_document, scan_top_level_spans
from .serializer_121 import ATTRIBUTE_ORDER, serialize_element, serialize_record
from .writer import LosslessPatchWriter, Patch

__all__ = [
    "ATTRIBUTE_ORDER",
    "DecodedEnvelope",
    "ElementSpan",
    "EnvelopeError",
    "EnvelopeState",
    "GsbDocument",
    "GsbError",
    "LosslessPatchWriter",
    "PasswordRequiredError",
    "Patch",
    "PatchConflictError",
    "UnsupportedFileVersionError",
    "decode_envelope",
    "encode_envelope",
    "inspect_envelope",
    "parse_document",
    "scan_top_level_spans",
    "serialize_element",
    "serialize_record",
]
