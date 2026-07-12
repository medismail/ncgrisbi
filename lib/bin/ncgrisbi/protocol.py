from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from typing import Any, BinaryIO, Dict, Iterable, List, Mapping, Optional, Tuple

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
from .mutations import (
    CreateCategory,
    CreateParty,
    CreateSubcategory,
    CreateTransaction,
    DeleteTransaction,
    MutationOperation,
    UpdateTransaction,
    apply_mutations,
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
        raise ProtocolError(
            "Framed payload length does not match payloadLength"
        )
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


def _strict_fields(
    operation: Mapping[str, Any],
    operation_type: str,
    allowed: Iterable[str],
) -> None:
    unknown = sorted(set(operation) - set(allowed) - {"type"})
    if unknown:
        raise ProtocolError(
            "%s contains unsupported fields: %s"
            % (operation_type, ", ".join(unknown))
        )


def _required(operation: Mapping[str, Any], field: str, operation_type: str) -> Any:
    if field not in operation:
        raise ProtocolError("%s requires %s" % (operation_type, field))
    return operation[field]


def _optional_bool(
    operation: Mapping[str, Any],
    field: str,
    default: bool = False,
) -> bool:
    if field not in operation:
        return default
    value = operation[field]
    if not isinstance(value, bool):
        raise ProtocolError("%s must be a JSON boolean" % field)
    return value


def _required_integer(
    operation: Mapping[str, Any],
    field: str,
    operation_type: str,
) -> int:
    value = _required(operation, field, operation_type)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProtocolError("%s must be a JSON integer" % field)
    return value


_UPDATE_CHANGE_FIELDS = {
    "accountId": "account_id",
    "date": "date",
    "valueDate": "value_date",
    "currencyId": "currency_id",
    "amount": "amount",
    "partyId": "party_id",
    "categoryId": "category_id",
    "subcategoryId": "subcategory_id",
    "note": "note",
    "paymentMethodId": "payment_method_id",
    "paymentReference": "payment_reference",
    "marked": "marked",
    "financialYear": "financial_year",
    "budgetId": "budget_id",
    "subbudgetId": "subbudget_id",
    "voucher": "voucher",
    "bankReference": "bank_reference",
}


def decode_operation(operation: Mapping[str, Any]) -> MutationOperation:
    if not isinstance(operation, Mapping):
        raise ProtocolError("Every mutation operation must be a JSON object")
    operation_type = operation.get("type")
    if not isinstance(operation_type, str):
        raise ProtocolError("Mutation operation type must be text")

    if operation_type == "createParty":
        allowed = {"name", "text", "search", "ignoreCase", "useRegex"}
        _strict_fields(operation, operation_type, allowed)
        return CreateParty(
            name=_required(operation, "name", operation_type),
            text=operation.get("text"),
            search=operation.get("search"),
            ignore_case=_optional_bool(operation, "ignoreCase"),
            use_regex=_optional_bool(operation, "useRegex"),
        )

    if operation_type == "createCategory":
        allowed = {"name", "kind"}
        _strict_fields(operation, operation_type, allowed)
        return CreateCategory(
            name=_required(operation, "name", operation_type),
            kind=_required_integer(operation, "kind", operation_type),
        )

    if operation_type == "createSubcategory":
        allowed = {"categoryId", "name"}
        _strict_fields(operation, operation_type, allowed)
        return CreateSubcategory(
            category_id=_required(operation, "categoryId", operation_type),
            name=_required(operation, "name", operation_type),
        )

    if operation_type == "createTransaction":
        allowed = {
            "accountId", "date", "amount", "paymentMethodId", "partyId",
            "categoryId", "subcategoryId", "note", "valueDate",
            "currencyId", "marked", "financialYear", "budgetId",
            "subbudgetId", "paymentReference", "voucher", "bankReference",
            "importedId",
        }
        _strict_fields(operation, operation_type, allowed)
        return CreateTransaction(
            account_id=_required(operation, "accountId", operation_type),
            date=_required(operation, "date", operation_type),
            amount=_required(operation, "amount", operation_type),
            payment_method_id=operation.get("paymentMethodId", "0"),
            party_id=operation.get("partyId", "0"),
            category_id=operation.get("categoryId", "0"),
            subcategory_id=operation.get("subcategoryId", "0"),
            note=operation.get("note"),
            value_date=operation.get("valueDate"),
            currency_id=operation.get("currencyId"),
            marked=operation.get("marked", 0),
            financial_year=operation.get("financialYear", "0"),
            budget_id=operation.get("budgetId", "0"),
            subbudget_id=operation.get("subbudgetId", "0"),
            payment_reference=operation.get("paymentReference"),
            voucher=operation.get("voucher"),
            bank_reference=operation.get("bankReference"),
            imported_id=operation.get("importedId"),
        )

    if operation_type == "updateTransaction":
        allowed = {"transactionId", "changes"}
        _strict_fields(operation, operation_type, allowed)
        changes = _required(operation, "changes", operation_type)
        if not isinstance(changes, Mapping):
            raise ProtocolError("updateTransaction changes must be a JSON object")
        unknown = sorted(set(changes) - set(_UPDATE_CHANGE_FIELDS))
        if unknown:
            raise ProtocolError(
                "updateTransaction contains unsupported changes: %s"
                % ", ".join(unknown)
            )
        translated = {
            _UPDATE_CHANGE_FIELDS[name]: value for name, value in changes.items()
        }
        return UpdateTransaction(
            transaction_id=_required(operation, "transactionId", operation_type),
            changes=translated,
        )

    if operation_type == "deleteTransaction":
        allowed = {"transactionId"}
        _strict_fields(operation, operation_type, allowed)
        return DeleteTransaction(
            transaction_id=_required(operation, "transactionId", operation_type)
        )

    raise ProtocolError("Unsupported mutation operation type: %s" % operation_type)


def decode_operations(raw_operations: Any) -> Tuple[MutationOperation, ...]:
    if not isinstance(raw_operations, list):
        raise ProtocolError("operations must be a JSON array")
    if len(raw_operations) > MAX_OPERATIONS:
        raise ProtocolError("Mutation batch exceeds the operation limit")
    return tuple(decode_operation(operation) for operation in raw_operations)


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


def execute_request(
    header: Mapping[str, Any],
    payload: bytes,
    password: Optional[str],
) -> Tuple[Dict[str, Any], bytes]:
    if header.get("version") != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol version")
    if header.get("command") != "mutate":
        raise ProtocolError("Unsupported protocol command")

    operations = decode_operations(header.get("operations"))
    result = apply_mutations(payload, operations, password=password)
    outcomes = [
        {
            "operationIndex": outcome.operation_index,
            "operation": outcome.operation,
            "recordType": outcome.record_type,
            "recordId": outcome.record_id,
        }
        for outcome in result.outcomes
    ]
    output = result.raw_bytes
    return (
        {
            "version": PROTOCOL_VERSION,
            "ok": True,
            "requestId": header.get("requestId"),
            "changed": output != payload,
            "sha256": hashlib.sha256(output).hexdigest(),
            "outcomes": outcomes,
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
    except Exception as exc:  # Every handled failure is returned as a valid frame.
        response_header = error_response(exc, request_id=request_id)
        response_payload = b""

    sys.stdout.buffer.write(encode_frame(response_header, response_payload))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
