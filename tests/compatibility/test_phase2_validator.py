from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi import (
    ValidationError,
    assert_valid_document,
    parse_document,
    validate_document,
)

FIXTURE = (
    ROOT
    / "tests"
    / "compatibility"
    / "fixtures"
    / "grisbi-1.2.2-basic.gsb"
)


def test_real_grisbi_fixture_is_semantically_valid() -> None:
    document = parse_document(FIXTURE.read_bytes())
    assert document.file_version == "1.2.1"
    assert document.grisbi_version == "1.2.2"
    assert validate_document(document) == ()
    assert_valid_document(document)


def test_duplicate_transaction_ids_are_reported() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Ac="2" Nb="4"',
        b'Ac="2" Nb="3"',
        1,
    )
    document = parse_document(raw)
    issues = validate_document(document)
    assert any(
        issue.code == "duplicate-id" and issue.tag == "Transaction"
        for issue in issues
    )
    with pytest.raises(ValidationError):
        assert_valid_document(document)


def test_missing_party_is_reported_but_existing_payment_number_remains_compatible() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Pa="1" Ca="1"',
        b'Pa="99" Ca="1"',
        1,
    )
    # Move transaction 4 to account 1 while retaining global payment number 7,
    # whose Payment record belongs to account 2. Existing Grisbi data remains
    # readable; account/sign restrictions apply when the selection is changed.
    raw = raw.replace(
        b'Ac="2" Nb="4"',
        b'Ac="1" Nb="4"',
        1,
    )
    document = parse_document(raw)
    codes = {issue.code for issue in validate_document(document)}
    assert "missing-party" in codes
    assert "missing-payment" not in codes


def test_missing_global_payment_number_is_reported() -> None:
    raw = FIXTURE.read_bytes().replace(b'Pn="3" Pc=', b'Pn="99" Pc=', 1)
    document = parse_document(raw)
    assert any(
        issue.code == "missing-payment"
        for issue in validate_document(document)
    )


def test_broken_transfer_is_a_nonfatal_compatibility_warning() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Trt="4" Mo="0"',
        b'Trt="99" Mo="0"',
        1,
    )
    document = parse_document(raw)
    warning = next(
        issue
        for issue in validate_document(document)
        if issue.code == "missing-transfer-target"
    )
    assert warning.severity == "warning"
    assert_valid_document(document)
