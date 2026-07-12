from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi import (
    CreateCategory,
    CreateParty,
    CreateSubcategory,
    CreateTransaction,
    DeleteTransaction,
    GsbIndex,
    MutationConflictError,
    MutationEngine,
    MutationError,
    UpdateTransaction,
    apply_mutations,
    parse_document,
)

FIXTURE = (
    ROOT
    / "tests"
    / "compatibility"
    / "fixtures"
    / "grisbi-1.2.2-basic.gsb"
)


def test_server_ids_use_global_maximum_not_xml_position() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Nb="12" Id="(null)" Dt="07/06/2026"',
        b'Nb="5" Id="(null)" Dt="07/06/2026"',
    )
    document = parse_document(raw)
    index = GsbIndex.build(document)

    assert index.next_transaction_id() == "12"
    assert index.next_party_id() == "3"
    assert index.next_category_id() == "3"
    assert index.next_subcategory_id("1") == "2"


def test_create_supported_records_with_server_allocated_ids() -> None:
    result = apply_mutations(
        FIXTURE.read_bytes(),
        [
            CreateParty('Landlord & Co', text="Rent"),
            CreateCategory("Food", kind=1),
            CreateSubcategory("1", "Water"),
            CreateTransaction(
                account_id="1",
                date="07/12/2026",
                value_date="07/13/2026",
                amount="-15.20",
                payment_method_id="1",
                party_id="1",
                category_id="1",
                subcategory_id="1",
                note='Phase 2 "test"',
                marked=1,
            ),
        ],
    )

    assert [outcome.record_id for outcome in result.outcomes] == [
        "3",
        "3",
        "2",
        "13",
    ]

    root = ET.fromstring(result.xml_bytes)
    assert root.findall("Party")[-1].attrib == {
        "Nb": "3",
        "Na": "Landlord & Co",
        "Txt": "Rent",
        "Search": "(null)",
        "IgnCase": "0",
        "UseRegex": "0",
    }
    assert root.findall("Category")[-1].get("Nb") == "3"
    assert any(
        node.get("Nbc") == "1" and node.get("Nb") == "2"
        for node in root.findall("Sub_category")
    )
    transaction = next(
        node
        for node in root.findall("Transaction")
        if node.get("Nb") == "13"
    )
    assert transaction.get("Am") == "-15.20"
    assert transaction.get("No") == 'Phase 2 "test"'
    assert result.raw_bytes == result.xml_bytes


def test_partial_update_preserves_hidden_metadata_and_changes_one_record() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)
    old_span = document.find_span("Transaction", "Nb", "10")
    assert old_span is not None
    old_element = document.element_for_span(old_span)
    assert old_element is not None
    old_attributes = dict(old_element.attrib)

    result = MutationEngine(document).apply(
        [
            UpdateTransaction(
                "10",
                {
                    "note": "Corrected invoice",
                    "amount": "-43.00",
                },
            )
        ]
    )
    updated = parse_document(result.raw_bytes)
    new_element = next(
        node
        for node in updated.root.findall("Transaction")
        if node.get("Nb") == "10"
    )

    for protected in (
        "Id",
        "Dv",
        "Re",
        "Fi",
        "Bu",
        "Sbu",
        "Vo",
        "Ba",
    ):
        assert new_element.get(protected) == old_attributes[protected]
    assert new_element.get("No") == "Corrected invoice"
    assert new_element.get("Am") == "-43.00"
    assert result.xml_bytes[:old_span.start] == original[:old_span.start]
    assert (
        result.xml_bytes[old_span.start:].count(
            b'<Transaction Ac="1" Nb="10"'
        )
        == 1
    )


def test_delete_removes_only_selected_transaction_line() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)
    span = document.find_span("Transaction", "Nb", "12")
    assert span is not None

    result = MutationEngine(document).apply([DeleteTransaction("12")])

    assert (
        result.xml_bytes
        == original[:span.line_start] + original[span.line_end:]
    )
    assert {
        node.get("Nb")
        for node in ET.fromstring(result.xml_bytes).findall("Transaction")
    } == {"10", "11"}


def test_invalid_second_operation_does_not_mutate_source_document() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)
    engine = MutationEngine(document)

    with pytest.raises(MutationError):
        engine.apply(
            [
                CreateParty("Valid new party"),
                CreateTransaction(
                    account_id="99",
                    date="07/12/2026",
                    amount="1.00",
                ),
            ]
        )

    assert document.raw_bytes == original
    assert document.xml_bytes == original
    assert document.root.findall("Party")[-1].get("Nb") == "2"


def test_rejects_wrong_category_sign_precision_and_payment_account() -> None:
    with pytest.raises(MutationError, match="debit category"):
        apply_mutations(
            FIXTURE.read_bytes(),
            [
                CreateTransaction(
                    account_id="1",
                    date="07/12/2026",
                    amount="-1.00",
                    category_id="2",
                    subcategory_id="1",
                    payment_method_id="1",
                )
            ],
        )

    with pytest.raises(MutationError, match="decimal places"):
        apply_mutations(
            FIXTURE.read_bytes(),
            [
                CreateTransaction(
                    account_id="1",
                    date="07/12/2026",
                    amount="1.001",
                    payment_method_id="1",
                )
            ],
        )

    with pytest.raises(MutationError, match="does not belong"):
        apply_mutations(
            FIXTURE.read_bytes(),
            [
                CreateTransaction(
                    account_id="1",
                    date="07/12/2026",
                    amount="1.00",
                    payment_method_id="2",
                )
            ],
        )


def test_protects_transfer_split_fields_and_duplicate_batch_targets() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'Trt="0" Mo="0" />',
        b'Trt="11" Mo="0" />',
        1,
    )
    raw = raw.replace(
        b'Trt="0" Mo="0" />',
        b'Trt="10" Mo="0" />',
        1,
    )
    document = parse_document(raw)

    with pytest.raises(MutationError, match="dedicated mutation phase"):
        MutationEngine(document).apply(
            [UpdateTransaction("10", {"note": "unsafe"})]
        )

    document = parse_document(FIXTURE.read_bytes())
    with pytest.raises(MutationConflictError):
        MutationEngine(document).apply(
            [
                UpdateTransaction("10", {"note": "first"}),
                UpdateTransaction("10", {"note": "second"}),
            ]
        )


def test_empty_batch_is_exact_noop() -> None:
    original = FIXTURE.read_bytes()
    result = apply_mutations(original, [])

    assert result.raw_bytes == original
    assert result.xml_bytes == original
    assert result.outcomes == ()
