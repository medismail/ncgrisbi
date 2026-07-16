from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Dict, Mapping, Optional, Tuple

from .errors import ConfirmationRequiredError, MarkStateError
from .parser import parse_document
from .phase6_engine import apply_phase6_operations
from .protocol import (
    MAX_OPERATIONS,
    PROTOCOL_VERSION,
    ProtocolError,
    encode_frame,
    error_response as base_error_response,
    read_frame,
    read_password_fd,
)
from .resolution import NameResolutionError
from .snapshot import build_account_snapshot
from .validator import assert_valid_document


def error_response(exc: Exception, request_id: Any = None) -> Dict[str, Any]:
    response = base_error_response(exc, request_id=request_id)
    if isinstance(exc, NameResolutionError):
        response["error"]["code"] = "name-resolution-error"
    elif isinstance(exc, ConfirmationRequiredError):
        response["error"]["code"] = "confirmation-required"
        response["error"]["reason"] = exc.reason
        response["error"]["transactionIds"] = list(exc.transaction_ids)
    elif isinstance(exc, MarkStateError):
        response["error"]["code"] = "marked-state-protected"
    return response


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


def _raw_operations(header: Mapping[str, Any]) -> list:
    operations = header.get("operations")
    if not isinstance(operations, list):
        raise ProtocolError("operations must be a JSON array")
    if not operations:
        raise ProtocolError("operations cannot be empty")
    if len(operations) > MAX_OPERATIONS:
        raise ProtocolError("Mutation batch exceeds the operation limit")
    for operation in operations:
        if not isinstance(operation, Mapping):
            raise ProtocolError("Every mutation operation must be a JSON object")
    return operations


def execute_request(
    header: Mapping[str, Any],
    payload: bytes,
    password: Optional[str],
) -> Tuple[Dict[str, Any], bytes]:
    if header.get("version") != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol version")

    command = header.get("command")
    if command == "accountSnapshot":
        document = parse_document(payload, password=password)
        assert_valid_document(document)
        snapshot = build_account_snapshot(document, _account_id(header))
        output = json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
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

    if command != "mutate":
        raise ProtocolError("Unsupported protocol command")

    result = apply_phase6_operations(
        payload,
        _raw_operations(header),
        password=password,
    )
    outcomes = []
    for expanded_index, outcome in enumerate(result.outcomes):
        mapped = dict(outcome)
        mapped["expandedOperationIndex"] = expanded_index
        outcomes.append(mapped)

    output = result.raw_bytes
    return (
        {
            "version": PROTOCOL_VERSION,
            "ok": True,
            "requestId": header.get("requestId"),
            "changed": output != payload,
            "sha256": hashlib.sha256(output).hexdigest(),
            "outcomes": outcomes,
            "warnings": list(result.warnings),
            "changedRecords": result.changed_records,
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
    return 0
