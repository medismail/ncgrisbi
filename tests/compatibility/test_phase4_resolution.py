from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi.mutations import (
    CreateCategory,
    CreateParty,
    CreateSubcategory,
    CreateTransaction,
    MutationEngine,
)
from ncgrisbi.parser import parse_document
from ncgrisbi.phase4_protocol import execute_request
from ncgrisbi.protocol import PROTOCOL_VERSION, decode_operation
from ncgrisbi.resolution import (
    NameResolutionError,
    normalize_name,
    plan_operations,
)
from ncgrisbi.serializer_121 import serialize_record

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"


def _document():
    return parse_document(FIXTURE.read_bytes())


def _transaction(**overrides):
    operation = {
        "type": "createTransaction",
        "accountId": "1",
        "date": "07/12/2026",
        "amount": "-12.50",
        "paymentMethodId": "1",
    }
    operation.update(overrides)
    return operation


def test_name_normalization_is_unicode_aware_but_not_accent_folding() -> None:
    assert normalize_name("  Café\tDU  Nord  ") == "café du nord"
    assert normalize_name("ＣＡＦＥ") == "cafe"
    assert normalize_name("Cafe") != normalize_name("Café")


def test_existing_references_are_reused_without_creating_records() -> None:
    plan = plan_operations(
        _document(),
        [
            _transaction(
                partyName=" electricity   & WATER ",
                categoryName=" housing ",
                subcategoryName=" ELECTRICITY ",
            )
        ],
        decode_operation,
    )

    assert len(plan.operations) == 1
    transaction = plan.operations[0]
    assert isinstance(transaction, CreateTransaction)
    assert transaction.party_id == "1"
    assert transaction.category_id == "1"
    assert transaction.subcategory_id == "1"


def test_missing_references_are_created_atomically_with_transaction() -> None:
    plan = plan_operations(
        _document(),
        [
            _transaction(
                partyName="Corner Shop",
                categoryName="Food",
                subcategoryName="Groceries",
                createMissing=True,
            )
        ],
        decode_operation,
    )

    assert [type(operation) for operation in plan.operations] == [
        CreateParty,
        CreateCategory,
        CreateSubcategory,
        CreateTransaction,
    ]
    assert plan.operations[1].kind == 1
    assert plan.operations[3].party_id == "3"
    assert plan.operations[3].category_id == "3"
    assert plan.operations[3].subcategory_id == "1"

    result = MutationEngine(_document()).apply(plan.operations)
    reopened = parse_document(result.raw_bytes)
    assert reopened.root.findall("Party")[-1].get("Na") == "Corner Shop"
    assert reopened.root.findall("Category")[-1].get("Na") == "Food"
    assert reopened.root.findall("Sub_category")[-1].get("Na") == "Groceries"
    created = reopened.root.findall("Transaction")[-1]
    assert created.get("Pa") == "3"
    assert created.get("Ca") == "3"
    assert created.get("Sca") == "1"


def test_repeated_names_in_one_batch_are_created_only_once() -> None:
    operation = _transaction(
        partyName="Batch Vendor",
        categoryName="Batch Category",
        subcategoryName="Batch Subcategory",
        createMissing=True,
    )
    second = dict(operation)
    second["date"] = "07/13/2026"

    plan = plan_operations(_document(), [operation, second], decode_operation)

    assert [type(operation) for operation in plan.operations] == [
        CreateParty,
        CreateCategory,
        CreateSubcategory,
        CreateTransaction,
        CreateTransaction,
    ]
    assert plan.operations[-1].party_id == "3"
    assert plan.operations[-1].category_id == "3"
    assert plan.operations[-1].subcategory_id == "1"


def test_explicit_create_earlier_in_batch_is_reused_by_name() -> None:
    plan = plan_operations(
        _document(),
        [
            {"type": "createParty", "name": "New Vendor"},
            _transaction(partyName=" new vendor "),
        ],
        decode_operation,
    )

    assert isinstance(plan.operations[0], CreateParty)
    assert plan.operations[1].party_id == "3"


def test_missing_name_requires_explicit_create_missing_opt_in() -> None:
    with pytest.raises(NameResolutionError, match="does not exist"):
        plan_operations(
            _document(),
            [_transaction(partyName="Typo Vendor")],
            decode_operation,
        )


def test_ambiguous_normalized_name_is_rejected_with_candidate_ids() -> None:
    duplicate = b"\t" + serialize_record(
        "Party",
        {
            "Nb": "3",
            "Na": " electricity   & water ",
            "Txt": None,
            "Search": None,
            "IgnCase": "0",
            "UseRegex": "0",
        },
    ) + b"\n"
    raw = FIXTURE.read_bytes().replace(
        b"\t<Category Nb=\"1\"",
        duplicate + b"\t<Category Nb=\"1\"",
        1,
    )
    document = parse_document(raw)

    with pytest.raises(NameResolutionError, match="matching IDs: 1, 3"):
        plan_operations(
            document,
            [_transaction(partyName="Electricity & Water")],
            decode_operation,
        )


def test_category_direction_is_derived_from_amount_and_conflicts_are_rejected() -> None:
    with pytest.raises(NameResolutionError, match="not with kind 1"):
        plan_operations(
            _document(),
            [_transaction(categoryName="Income")],
            decode_operation,
        )

    plan = plan_operations(
        _document(),
        [
            _transaction(
                amount="125.00",
                categoryName="Bonus",
                createMissing=True,
            )
        ],
        decode_operation,
    )
    assert isinstance(plan.operations[0], CreateCategory)
    assert plan.operations[0].kind == 0


def test_zero_amount_requires_category_kind_only_when_category_must_be_created() -> None:
    with pytest.raises(NameResolutionError, match="categoryKind is required"):
        plan_operations(
            _document(),
            [
                _transaction(
                    amount="0.00",
                    categoryName="Zero Category",
                    createMissing=True,
                )
            ],
            decode_operation,
        )

    plan = plan_operations(
        _document(),
        [
            _transaction(
                amount="0.00",
                categoryName="Zero Category",
                categoryKind=1,
                createMissing=True,
            )
        ],
        decode_operation,
    )
    assert isinstance(plan.operations[0], CreateCategory)
    assert plan.operations[0].kind == 1


def test_ids_and_names_are_mutually_exclusive() -> None:
    with pytest.raises(NameResolutionError, match="either partyId or partyName"):
        plan_operations(
            _document(),
            [_transaction(partyId="1", partyName="Vendor")],
            decode_operation,
        )


def test_phase4_protocol_maps_expanded_outcomes_to_client_operation() -> None:
    header = {
        "version": PROTOCOL_VERSION,
        "command": "mutate",
        "requestId": "phase4-request",
        "operations": [
            _transaction(
                partyName="Protocol Vendor",
                categoryName="Protocol Category",
                subcategoryName="Protocol Subcategory",
                createMissing=True,
            )
        ],
    }

    response, output = execute_request(header, FIXTURE.read_bytes(), None)

    assert response["ok"] is True
    assert response["requestId"] == "phase4-request"
    assert output != FIXTURE.read_bytes()
    assert [outcome["role"] for outcome in response["outcomes"]] == [
        "party",
        "category",
        "subcategory",
        "transaction",
    ]
    assert all(outcome["operationIndex"] == 0 for outcome in response["outcomes"])
    assert [outcome["autoCreated"] for outcome in response["outcomes"]] == [
        True,
        True,
        True,
        False,
    ]
