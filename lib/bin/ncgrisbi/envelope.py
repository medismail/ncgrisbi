from __future__ import annotations

import gzip
import importlib
from dataclasses import dataclass
from typing import Optional

from .errors import EnvelopeError, PasswordRequiredError

GZIP_MAGIC = b"\x1f\x8b"
V2_MARKER = b"Grisbi encryption v2: "


@dataclass(frozen=True)
class EnvelopeState:
    compressed: bool = False
    encrypted: bool = False


@dataclass(frozen=True)
class DecodedEnvelope:
    xml_bytes: bytes
    state: EnvelopeState


def _load_crypto_module():
    """Load the legacy Grisbi v2 codec lazily.

    Plain and gzip-only files must remain usable even when the optional DES
    dependency is not installed. The module is loaded only for encrypted data.
    """
    return importlib.import_module("gsb_decode")


def _decompress(raw_bytes: bytes) -> bytes:
    try:
        return gzip.decompress(raw_bytes)
    except (OSError, EOFError) as exc:
        raise EnvelopeError("Invalid gzip-wrapped GSB file") from exc


def inspect_envelope(raw_bytes: bytes) -> EnvelopeState:
    if not isinstance(raw_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("raw_bytes must be bytes-like")

    payload = bytes(raw_bytes)
    compressed = payload.startswith(GZIP_MAGIC)
    if compressed:
        payload = _decompress(payload)

    return EnvelopeState(
        compressed=compressed,
        encrypted=payload.startswith(V2_MARKER),
    )


def decode_envelope(raw_bytes: bytes, password: Optional[str] = None) -> DecodedEnvelope:
    payload = bytes(raw_bytes)
    state = inspect_envelope(payload)

    if state.compressed:
        payload = _decompress(payload)

    if state.encrypted:
        if not password:
            raise PasswordRequiredError("A password is required for this encrypted GSB file")
        try:
            payload = _load_crypto_module().decrypt_v2(password, payload)
        except PasswordRequiredError:
            raise
        except Exception as exc:
            raise EnvelopeError("Unable to decrypt GSB file") from exc

    return DecodedEnvelope(xml_bytes=payload, state=state)


def encode_envelope(
    xml_bytes: bytes,
    state: EnvelopeState,
    password: Optional[str] = None,
) -> bytes:
    payload = bytes(xml_bytes)

    # Grisbi 1.2.2 writes XML -> encryption -> gzip. Read performs the exact
    # reverse order, which also allows gzip-wrapped encrypted files to be found.
    if state.encrypted:
        if not password:
            raise PasswordRequiredError("A password is required to write this encrypted GSB file")
        try:
            payload = _load_crypto_module().encrypt_v2(password, payload)
        except PasswordRequiredError:
            raise
        except Exception as exc:
            raise EnvelopeError("Unable to encrypt GSB file") from exc

    if state.compressed:
        # A fixed mtime makes newly generated envelopes deterministic. A no-op
        # write never reaches this path; it returns the original raw bytes.
        payload = gzip.compress(payload, mtime=0)

    return payload
