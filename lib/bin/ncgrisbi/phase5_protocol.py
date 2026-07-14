from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Dict, Mapping, Optional, Tuple

from .compat_engine import apply_compat_operations
from .parser import parse_document
from .protocol import (
    MAX_OPERATIONS,
    PROTOCOL_VERSION,
    ProtocolError,
    decode_operation,
    encode_frame,
    error_response as base_error_response,
    read_frame,
    read_password_fd,
)
from .resolution import NameResolutionError, plan_operations
from .snapshot import build_account_snapshot
from .transfers import apply_transfer
from .validator import assert_valid_document


def error_response(exc: Exception, request_id: Any = None) -> Dict[str, Any]:
    response = base_error_response(exc, request_id=request_id)
    if isinstance(exc, NameResolutionError):
        response["error"]["code"] = "name-resolution-error"
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
    return operations


def _normal_operation(
    document: Any,
    raw: Mapping[str, Any],
    operation_index: int,
    password: Optional[str],
):
    plan = plan_operations(document, [raw], decode_operation)
    result = apply_compat_operations(
        document,
        plan.operations,
        password=password,
    )
    outcomes = []
    for expanded_index, (outcome, planned) in enumerate(
        zip(result.outcomes, plan.mutations)
    ):
        outcomes.append(
            {
                "operationIndex": operation_index,
                "expandedOperationIndex": expanded_index,
                "operation": outcome.operation,
                "recordType": outcome.record_type,
                "recordId": outcome.record_id,
                "role": planned.role,
                "autoCreated": planned.auto_created,
            }
        )
    return result.raw_bytes, outcomes


def _transfer_operation(
    document: Any,
    raw: Mapping[str, Any],
    operation_index: int,
    password: Optional[str],
):
    result = apply_transfer(document, raw, password=password)
    outcomes = [
        {
            "operationIndex": operation_index,
            "expandedOperationIndex": expanded_index,
            "operation": outcome.operation,
            "recordType": outcome.record_type,
            "recordId": outcome.record_id,
            "role": outcome.role,
            "autoCreated": outcome.role == "party",
        }
        for expanded_index, outcome in enumerate(result.outcomes)
    ]
    return result.raw_bytes, outcomes


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

    current = payload
    all_outcomes = []
    for operation_index, raw in enumerate(_raw_operations(header)):
        if not isinstance(raw, Mapping):
            raise ProtocolError(
                "Every mutation operation must be a JSON object"
            )
        document = parse_document(current, password=password)
        if raw.get("type") in (
            "createTransfer",
            "updateTransfer",
            "deleteTransfer",
        ):
            current, outcomes = _transfer_operation(
                document,
                raw,
                operation_index,
                password,
            )
        else:
            current, outcomes = _normal_operation(
                document,
                raw,
                operation_index,
                password,
            )
        base_index = len(all_outcomes)
        for offset, outcome in enumerate(outcomes):
            outcome["expandedOperationIndex"] = base_index + offset
        all_outcomes.extend(outcomes)

    return (
        {
            "version": PROTOCOL_VERSION,
            "ok": True,
            "requestId": header.get("requestId"),
            "changed": current != payload,
            "sha256": hashlib.sha256(current).hexdigest(),
            "outcomes": all_outcomes,
        },
        current,
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
