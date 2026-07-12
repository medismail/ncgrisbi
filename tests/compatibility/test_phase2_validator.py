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


def test_phase0_fixture_is_semantically_valid() -> None:
    document = parse_document(FIXTURE.read_bytes())
    assert validate_document(document) == ()
    assert_valid_document(document)


def test_duplicate_transaction_ids_are_reported() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Nb="12" Id="(null)" Dt="07/06/2026"',
        b'Nb="11" Id="(null)" Dt="07/06/2026"',
    )
    document = parse_document(raw)
    issues = validate_document(document)
    assert any(
        issue.code == "duplicate-id" and issue.tag == "Transaction"
        for issue in issues
    )
    with pytest.raises(ValidationError):
        assert_valid_document(document)


def test_missing_party_and_wrong_payment_account_are_reported() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Pa="1" Ca="1"',
        b'Pa="99" Ca="1"',
        1,
    )
    raw = raw.replace(
        b'Ac="2" Nb="12"',
        b'Ac="1" Nb="12"',
        1,
    )
    document = parse_document(raw)
    codes = {issue.code for issue in validate_document(document)}
    assert "missing-party" in codes
    assert "missing-payment" in codes


def test_nonreciprocal_transfer_is_reported() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Trt="0" Mo="0" />',
        b'Trt="11" Mo="0" />',
        1,
    )
    document = parse_document(raw)
    assert any(
        issue.code == "nonreciprocal-transfer"
        for issue in validate_document(document)
    )
