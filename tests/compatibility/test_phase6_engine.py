from __future__ import annotations

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi import phase6_engine
from ncgrisbi.errors import (
    ConfirmationRequiredError,
    MarkStateError,
    MutationError,
)
from ncgrisbi.parser import parse_document
from ncgrisbi.phase5_protocol import execute_request
from ncgrisbi.phase6_engine import apply_phase6_operations
from ncgrisbi.protocol import PROTOCOL_VERSION
from ncgrisbi.snapshot import build_account_snapshot
from ncgrisbi.validator import assert_valid_document, warning_issues

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-real.gsb"


def _root(raw: bytes) -> ET.Element:
    return ET.fromstring(raw)


def _transaction(raw: bytes, transaction_id: str) -> ET.Element:
    return next(
        element
        for element in _root(raw).findall("Transaction")
        if element.get("Nb") == str(transaction_id)
    )


def _transaction_line(transaction_id: int) -> bytes:
    return (
        '\t<Transaction Ac="1" Nb="%d" Id="(null)" Dt="07/13/2026" '
        'Dv="(null)" Cu="1" Am="-1.00" Exb="0" Exr="0.00" Exf="0.00" '
        'Pa="1" Ca="1" Sca="7" Br="0" No="(null)" Pn="3" Pc="(null)" '
        'Ma="0" Ar="0" Au="0" Re="0" Fi="0" Bu="0" Sbu="0" '
        'Vo="(null)" Ba="(null)" Trt="0" Mo="0" />\n'
    ) % transaction_id


def _with_extra_transactions(raw: bytes, first: int, last: int) -> bytes:
    extra = b"".join(_transaction_line(number).encode("utf-8") for number in range(first, last + 1))
    return raw.replace(b'\t<Party Nb="1"', extra + b'\t<Party Nb="1"', 1)


def _mark_transaction(raw: bytes, transaction_id: str, mark: str, reconcile: str) -> bytes:
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if ('Nb="%s"' % transaction_id).encode("ascii") in line and b"<Transaction " in line:
            lines[index] = re.sub(
                rb'Ma="[0-3]" Ar="0" Au="0" Re="[0-9]+"',
                ('Ma="%s" Ar="0" Au="0" Re="%s"' % (mark, reconcile)).encode("ascii"),
                line,
                count=1,
            )
            break
    return b"".join(lines)


def test_real_fixture_contains_reciprocal_grisbi_122_transfer() -> None:
    document = parse_document(FIXTURE.read_bytes())
    assert document.file_version == "1.2.1"
    assert document.grisbi_version == "1.2.2"
    assert_valid_document(document)
    assert _transaction(FIXTURE.read_bytes(), "3").get("Trt") == "4"
    assert _transaction(FIXTURE.read_bytes(), "4").get("Trt") == "3"


def test_mixed_batch_is_parsed_once_and_rendered_once(monkeypatch) -> None:
    calls = 0
    original_parse = phase6_engine.parse_document

    def counting_parse(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(phase6_engine, "parse_document", counting_parse)
    result = apply_phase6_operations(
        FIXTURE.read_bytes(),
        [
            {
                "type": "createTransfer",
                "accountId": "1",
                "targetAccountId": "2",
                "date": "07/14/2026",
                "amount": "-10.00",
                "partyId": "1",
                "paymentMethodId": "3",
                "targetPaymentMethodId": "7",
            },
            {
                "type": "updateTransfer",
                "transactionId": "3",
                "changes": {"amount": "-45.00", "note": "moved"},
            },
            {"type": "deleteTransaction", "transactionId": "1"},
        ],
    )

    assert calls == 2
    assert _transaction(result.raw_bytes, "3").get("Am") == "-45.00"
    assert _transaction(result.raw_bytes, "4").get("Am") == "45.00"
    assert {
        element.get("Nb") for element in _root(result.raw_bytes).findall("Transaction")
    } == {"2", "3", "4", "5", "6"}
    assert result.changed_records == 5


def test_existing_transfer_can_be_edited_from_counterpart_account() -> None:
    result = apply_phase6_operations(
        FIXTURE.read_bytes(),
        [
            {
                "type": "updateTransfer",
                "transactionId": "4",
                "changes": {"amount": "50.00", "date": "07/15/2026"},
            }
        ],
    )
    assert _transaction(result.raw_bytes, "4").get("Am") == "50.00"
    assert _transaction(result.raw_bytes, "3").get("Am") == "-50.00"
    assert _transaction(result.raw_bytes, "3").get("Dt") == "07/15/2026"


def test_normal_transaction_can_be_converted_to_transfer_and_back() -> None:
    first = apply_phase6_operations(
        FIXTURE.read_bytes(),
        [
            {
                "type": "convertTransactionToTransfer",
                "transactionId": "1",
                "targetAccountId": "2",
                "paymentMethodId": "3",
                "targetPaymentMethodId": "7",
            }
        ],
    )
    source = _transaction(first.raw_bytes, "1")
    counterpart_id = source.get("Trt")
    counterpart = _transaction(first.raw_bytes, counterpart_id)
    assert source.get("Ca") == "0"
    assert source.get("Sca") == "0"
    assert counterpart.get("Trt") == "1"
    assert counterpart.get("Am") == "5.00"

    second = apply_phase6_operations(
        first.raw_bytes,
        [
            {
                "type": "convertTransferToTransaction",
                "transactionId": "1",
                "categoryId": "1",
                "subcategoryId": "7",
            }
        ],
    )
    restored = _transaction(second.raw_bytes, "1")
    assert restored.get("Trt") == "0"
    assert restored.get("Ca") == "1"
    assert restored.get("Sca") == "7"
    assert counterpart_id not in {
        element.get("Nb") for element in _root(second.raw_bytes).findall("Transaction")
    }


def test_reconciled_transfer_requires_explicit_confirmation() -> None:
    raw = _mark_transaction(FIXTURE.read_bytes(), "3", "3", "8")
    with pytest.raises(ConfirmationRequiredError) as caught:
        apply_phase6_operations(
            raw,
            [{"type": "deleteTransfer", "transactionId": "3"}],
        )
    assert caught.value.reason == "reconciled-transaction"
    assert caught.value.transaction_ids == ("3",)

    result = apply_phase6_operations(
        raw,
        [
            {
                "type": "deleteTransfer",
                "transactionId": "3",
                "allowReconciled": True,
            }
        ],
    )
    assert {element.get("Nb") for element in _root(result.raw_bytes).findall("Transaction")} == {"1", "2"}


def test_broken_transfer_is_visible_as_warning_and_read_only() -> None:
    raw = FIXTURE.read_bytes().replace(b'Trt="4" Mo="0"', b'Trt="99" Mo="0"', 1)
    document = parse_document(raw)
    assert_valid_document(document)
    assert any(issue.code == "missing-transfer-target" for issue in warning_issues(document))
    snapshot = build_account_snapshot(document, "1")
    assert snapshot["W"][0][0] == "missing-transfer-target"
    broken = next(item for item in snapshot["T"] if item[0] == "3")
    assert broken[16] & 8
    with pytest.raises(MutationError, match="not a valid reciprocal transfer"):
        apply_phase6_operations(
            raw,
            [
                {
                    "type": "updateTransfer",
                    "transactionId": "3",
                    "changes": {"amount": "-41.00"},
                }
            ],
        )


def test_quick_mark_batch_changes_only_ma_attribute_values() -> None:
    raw = _with_extra_transactions(FIXTURE.read_bytes(), 5, 64)
    marks = [[str(number), 1] for number in range(1, 65)]
    result = apply_phase6_operations(
        raw,
        [{"type": "setTransactionMarks", "marks": marks}],
    )
    assert result.changed_records == 64
    assert all(
        _transaction(result.raw_bytes, str(number)).get("Ma") == "1"
        for number in range(1, 65)
    )
    normalized_before = re.sub(rb'Ma="[01]"', b'Ma="X"', raw)
    normalized_after = re.sub(rb'Ma="[01]"', b'Ma="X"', result.raw_bytes)
    assert normalized_after == normalized_before


def test_quick_mark_rejects_telepointed_or_reconciled_rows() -> None:
    raw = _mark_transaction(FIXTURE.read_bytes(), "1", "3", "7")
    with pytest.raises(MarkStateError):
        apply_phase6_operations(
            raw,
            [{"type": "setTransactionMarks", "marks": [["1", 0]]}],
        )


def test_mark_and_structural_update_merge_into_one_record_patch() -> None:
    result = apply_phase6_operations(
        FIXTURE.read_bytes(),
        [
            {
                "type": "updateTransaction",
                "transactionId": "1",
                "changes": {"note": "edited"},
            },
            {"type": "setTransactionMarks", "marks": [["1", 1]]},
        ],
    )
    item = _transaction(result.raw_bytes, "1")
    assert item.get("No") == "edited"
    assert item.get("Ma") == "1"
    assert result.changed_records == 1


def test_protocol_reports_quick_mark_outcome_and_changed_records() -> None:
    header, payload = execute_request(
        {
            "version": PROTOCOL_VERSION,
            "command": "mutate",
            "requestId": "phase6-mark",
            "operations": [
                {"type": "setTransactionMarks", "marks": [["1", 1], ["2", 1]]}
            ],
        },
        FIXTURE.read_bytes(),
        None,
    )
    assert header["ok"] is True
    assert header["changedRecords"] == 2
    assert header["outcomes"][0]["operation"] == "SetTransactionMarks"
    assert header["outcomes"][0]["changedCount"] == 2
    assert _transaction(payload, "1").get("Ma") == "1"
