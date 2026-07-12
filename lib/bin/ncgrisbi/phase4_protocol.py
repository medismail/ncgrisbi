from __future__ import annotations

import hashlib
import sys
from typing import Any, Dict, Mapping, Optional, Tuple

from .mutations import MutationEngine
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
from .resolution import NameResolutionError, ResolutionPlan, plan_operations


def error_response(exc: Exception, request_id: Any = None) -> Dict[str, Any]:
    response = base_error_response(exc, request_id=request_id)
    if isinstance(exc, NameResolutionError):
        response["error"]["code"] = "name-resolution-error"
    return response


def _raw_operations(header: Mapping[str, Any]) -> list:
    operations = header.get("operations")
    if not isinstance(operations, list):
        raise ProtocolError("operations must be a JSON array")
    if len(operations) > MAX_OPERATIONS:
        raise ProtocolError("Mutation batch exceeds the operation limit")
    return operations


def _outcomes(result: Any, plan: ResolutionPlan) -> list:
    if len(result.outcomes) != len(plan.mutations):
        raise ProtocolError("Mutation outcome count does not match the resolution plan")
    response = []
    for expanded_index, (outcome, planned) in enumerate(
        zip(result.outcomes, plan.mutations)
    ):
        response.append(
            {
                "operationIndex": planned.client_operation_index,
                "expandedOperationIndex": expanded_index,
                "operation": outcome.operation,
                "recordType": outcome.record_type,
                "recordId": outcome.record_id,
                "role": planned.role,
                "autoCreated": planned.auto_created,
            }
        )
    return response


def execute_request(
    header: Mapping[str, Any],
    payload: bytes,
    password: Optional[str],
) -> Tuple[Dict[str, Any], bytes]:
    if header.get("version") != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol version")
    if header.get("command") != "mutate":
        raise ProtocolError("Unsupported protocol command")

    document = parse_document(payload, password=password)
    plan = plan_operations(document, _raw_operations(header), decode_operation)
    result = MutationEngine(document).apply(plan.operations, password=password)
    output = result.raw_bytes
    return (
        {
            "version": PROTOCOL_VERSION,
            "ok": True,
            "requestId": header.get("requestId"),
            "changed": output != payload,
            "sha256": hashlib.sha256(output).hexdigest(),
            "outcomes": _outcomes(result, plan),
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
    return 0 if response_header.get("ok") else 1
