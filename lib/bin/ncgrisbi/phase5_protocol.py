from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Dict, Mapping, Optional, Tuple

from .phase4_protocol import error_response, execute_request as execute_phase4_request
from .parser import parse_document
from .protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    encode_frame,
    read_frame,
    read_password_fd,
)
from .snapshot import build_account_snapshot
from .validator import assert_valid_document


def _account_id(header: Mapping[str, Any]) -> str:
    value = header.get("accountId")
    if not isinstance(value, str):
        raise ProtocolError("accountId must be a canonical positive identifier")
    try:
        number = int(value)
    except ValueError:
        raise ProtocolError("accountId must be a canonical positive identifier")
    if number <= 0 or str(number) != value:
        raise ProtocolError("accountId must be a canonical positive identifier")
    return value


def execute_request(
    header: Mapping[str, Any],
    payload: bytes,
    password: Optional[str],
) -> Tuple[Dict[str, Any], bytes]:
    if header.get("version") != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol version")

    command = header.get("command")
    if command == "mutate":
        return execute_phase4_request(header, payload, password)
    if command != "accountSnapshot":
        raise ProtocolError("Unsupported protocol command")

    document = parse_document(payload, password=password)
    assert_valid_document(document)
    snapshot = build_account_snapshot(document, _account_id(header))
    output = json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return (
        {
            "version": PROTOCOL_VERSION,
            "ok": True,
            "requestId": header.get("requestId"),
            "changed": False,
            "contentType": "application/json",
            "sha256": hashlib.sha256(output).hexdigest(),
        },
        output,
    )


def main() -> int:
    request_id = None
    try:
        header, payload = read_frame(sys.stdin.buffer)
        request_id = header.get("requestId")
        password = read_password_fd(3)
        response_header, response_payload = execute_request(
            header,
            payload,
            password,
        )
    except Exception as exc:
        response_header = error_response(exc, request_id=request_id)
        response_payload = b""

    sys.stdout.buffer.write(encode_frame(response_header, response_payload))
    sys.stdout.buffer.flush()
    # A framed domain error is a successful protocol exchange. PHP decodes the
    # stable error code instead of replacing it with a generic process failure.
    return 0
