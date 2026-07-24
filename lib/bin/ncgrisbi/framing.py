from __future__ import annotations

import json
import os
import struct
from typing import Any, BinaryIO, Dict, List, Mapping, Optional, Tuple

from .errors import (
    EnvelopeError,
    GsbError,
    MutationConflictError,
    MutationError,
    PasswordRequiredError,
    RecordNotFoundError,
    UnsupportedFileVersionError,
    ValidationError,
)

PROTOCOL_VERSION = 1
MAX_HEADER_BYTES = 8 * 1024 * 1024
MAX_OPERATIONS = 1000
MAX_PASSWORD_BYTES = 64 * 1024


class ProtocolError(Exception):
    """Raised when the PHP/Python transport frame is malformed."""


def _read_exact(stream: BinaryIO, length: int) -> bytes:
    chunks: List[bytes] = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ProtocolError("Unexpected end of framed input")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(stream: BinaryIO) -> Tuple[Dict[str, Any], bytes]:
    prefix = _read_exact(stream, 4)
    (header_length,) = struct.unpack("!I", prefix)
    if header_length <= 0 or header_length > MAX_HEADER_BYTES:
        raise ProtocolError("Protocol header length is outside the allowed range")

    header_bytes = _read_exact(stream, header_length)
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("Protocol header is not valid UTF-8 JSON") from exc
    if not isinstance(header, dict):
        raise ProtocolError("Protocol header must be a JSON object")

    payload = stream.read()
    expected_length = header.get("payloadLength")
    if not isinstance(expected_length, int) or expected_length < 0:
        raise ProtocolError("payloadLength must be a non-negative integer")
    if expected_length != len(payload):
        raise ProtocolError("Framed payload length does not match payloadLength")
    return header, payload


def encode_frame(header: Mapping[str, Any], payload: bytes = b"") -> bytes:
    response = dict(header)
    response["payloadLength"] = len(payload)
    header_bytes = json.dumps(
        response,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise ProtocolError("Protocol response header is too large")
    return struct.pack("!I", len(header_bytes)) + header_bytes + bytes(payload)


def read_password_fd(fd: int = 3) -> Optional[str]:
    chunks: List[bytes] = []
    total = 0
    try:
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_PASSWORD_BYTES:
                raise ProtocolError("Password exceeds the transport limit")
            chunks.append(chunk)
    except OSError as exc:
        raise ProtocolError("Unable to read the password descriptor") from exc

    raw = b"".join(chunks)
    if not raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Password descriptor is not valid UTF-8") from exc


def _issue_to_json(issue: Any) -> Dict[str, Any]:
    return {
        "code": getattr(issue, "code", "validation-error"),
        "message": getattr(issue, "message", str(issue)),
        "tag": getattr(issue, "tag", None),
        "recordId": getattr(issue, "record_id", None),
    }


def error_response(exc: Exception, request_id: Any = None) -> Dict[str, Any]:
    code = "internal-error"
    error_type = type(exc).__name__
    details: Dict[str, Any] = {}

    if isinstance(exc, ProtocolError):
        code = "invalid-protocol"
    elif isinstance(exc, ValidationError):
        code = "validation-error"
        details["issues"] = [_issue_to_json(issue) for issue in exc.issues]
    elif isinstance(exc, RecordNotFoundError):
        code = "record-not-found"
    elif isinstance(exc, MutationConflictError):
        code = "mutation-conflict"
    elif isinstance(exc, MutationError):
        code = "invalid-mutation"
    elif isinstance(exc, PasswordRequiredError):
        code = "password-required"
    elif isinstance(exc, UnsupportedFileVersionError):
        code = "unsupported-file-version"
    elif isinstance(exc, EnvelopeError):
        code = "envelope-error"
    elif isinstance(exc, GsbError):
        code = "gsb-error"

    message = str(exc) or error_type
    if code == "internal-error":
        message = "The Grisbi protocol worker failed internally"
    error = {
        "type": error_type,
        "code": code,
        "message": message,
    }
    error.update(details)
    return {
        "version": PROTOCOL_VERSION,
        "ok": False,
        "requestId": request_id,
        "error": error,
    }
