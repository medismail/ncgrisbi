"""Existing-transaction edits can create their missing references atomically."""
from __future__ import annotations

import pytest

from test_phase_a_backend import fixture_bytes

from ncgrisbi.errors import MutationError
from ncgrisbi.mutation import apply_mutations
from ncgrisbi.parser import parse_document
from ncgrisbi.validator import assert_valid_document


def edit(transaction_id="1", **changes):
    return {"type": "updateTransaction", "transactionId": transaction_id, "changes": changes}


def nodes(result, tag):
    return parse_document(result.raw_bytes).root.findall(tag)


def test_existing_expense_creates_party_category_subcategory_and_preserves_id():
    original = fixture_bytes()
    result = apply_mutations(original, [edit(
        partyName="New Plumber", categoryName="Repairs",
        subcategoryName="Pipes", createMissing=True,
    )])
    document = parse_document(result.raw_bytes)
    assert_valid_document(document)
    parties = document.root.findall("Party")
    categories = document.root.findall("Category")
    subcategories = document.root.findall("Sub_category")
    transactions = document.root.findall("Transaction")

    assert [(p.get("Nb"), p.get("Na")) for p in parties][-1] == ("2", "New Plumber")
    assert (categories[-1].get("Nb"), categories[-1].get("Na"), categories[-1].get("Kd")) == ("2", "Repairs", "1")
    assert (subcategories[-1].get("Nbc"), subcategories[-1].get("Nb"), subcategories[-1].get("Na")) == ("2", "1", "Pipes")
    assert (transactions[0].get("Nb"), transactions[0].get("Pa"), transactions[0].get("Ca"), transactions[0].get("Sca")) == ("1", "2", "2", "1")
    assert transactions[1].get("Pa") == "1"
    assert result.account_totals == {"1": {"total_amount": -10.0, "total_marked_amount": -10.0}}
    assert {x["type"] for x in result.outcomes} == {
        "CreateParty", "CreateCategory", "CreateSubcategory", "UpdateTransaction"
    }


def test_existing_category_can_gain_subcategory_without_creating_category():
    result = apply_mutations(fixture_bytes(), [edit(
        categoryId="1", subcategoryName="Takeout", createMissing=True,
    )])
    assert len(nodes(result, "Category")) == 1
    subcats = nodes(result, "Sub_category")
    assert len(subcats) == 2
    assert (subcats[-1].get("Nbc"), subcats[-1].get("Nb")) == ("1", "2")
    assert nodes(result, "Transaction")[0].get("Sca") == "2"


def test_updating_only_subcategory_uses_saved_category():
    result = apply_mutations(fixture_bytes(), [edit(
        subcategoryName="Lunch", createMissing=True,
    )])
    assert nodes(result, "Transaction")[0].get("Ca") == "1"
    assert nodes(result, "Transaction")[0].get("Sca") == "2"


def test_changing_category_clears_old_subcategory():
    result = apply_mutations(fixture_bytes(), [edit(
        categoryName="Utilities", createMissing=True,
    )])
    updated = nodes(result, "Transaction")[0]
    assert updated.get("Ca") == "2"
    assert updated.get("Sca") == "0"


def test_missing_names_reused_in_one_batch_and_existing_names_reused():
    result = apply_mutations(fixture_bytes(), [
        edit("1", partyName="New Bakery", categoryName="Bread",
             subcategoryName="Morning", createMissing=True),
        edit("2", partyName=" new bakery ", categoryName=" bread ",
             subcategoryName=" morning ", createMissing=True),
    ])
    assert len(nodes(result, "Party")) == 2
    assert len(nodes(result, "Category")) == 2
    assert len(nodes(result, "Sub_category")) == 2
    tx1, tx2 = nodes(result, "Transaction")
    assert [tx1.get(field) for field in ("Pa", "Ca", "Sca")] == [
        tx2.get(field) for field in ("Pa", "Ca", "Sca")
    ]

    reused = apply_mutations(fixture_bytes(), [
        edit(partyName=" shop ", categoryName=" food ",
             subcategoryName=" groceries "),
    ])
    assert len(nodes(reused, "Party")) == 1
    assert len(nodes(reused, "Category")) == 1
    assert len(nodes(reused, "Sub_category")) == 1


@pytest.mark.parametrize("changes,expected_error", [
    ({"partyName": "Absent"}, "does not exist"),
    ({"categoryName": "Absent"}, "does not exist"),
    ({"subcategoryName": "Absent"}, "does not exist"),
    ({"partyId": "1", "partyName": "Any", "createMissing": True}, "either partyId or partyName"),
    ({"categoryId": "1", "categoryName": "Any", "createMissing": True}, "either categoryId or categoryName"),
    ({"categoryId": "1", "subcategoryId": "1", "subcategoryName": "Any"}, "either subcategoryId or subcategoryName"),
    ({"createMissing": True, "partyId": "1"}, "requires a name-based reference"),
    ({"partyName": "Any", "createMissing": "true"}, "must be a JSON boolean"),
    ({"amount": "15.00", "categoryName": "Food", "createMissing": True}, "not with the required kind"),
    ({"amount": "0", "categoryName": "Zero", "createMissing": True}, "categoryKind is required"),
])
def test_invalid_edits_fail_without_written_document(changes, expected_error):
    original = fixture_bytes()
    with pytest.raises(MutationError, match=expected_error):
        apply_mutations(original, [edit(**changes)])
    assert original == fixture_bytes()


def test_income_category_kind_from_updated_positive_amount():
    result = apply_mutations(fixture_bytes(), [edit(
        amount="12.00", paymentMethodId="0",
        categoryName="Salary", categoryKind=0, createMissing=True,
    )])
    assert nodes(result, "Category")[-1].get("Kd") == "0"
    assert nodes(result, "Transaction")[0].get("Am") == "12.00"


def test_transfer_update_creates_payee_on_both_sides():
    source = apply_mutations(fixture_bytes(), [{
        "type": "createTransfer", "accountId": "1", "targetAccountId": "2",
        "date": "01/03/2026", "amount": "-4.00",
        "paymentMethodId": "1", "targetPaymentMethodId": "0",
    }])
    new_tx = nodes(source, "Transaction")[-2]
    updated = apply_mutations(source.raw_bytes, [{
        "type": "updateTransfer", "transactionId": new_tx.get("Nb"),
        "changes": {"partyName": "Interbank", "createMissing": True},
    }])
    created_party = nodes(updated, "Party")[-1]
    both = nodes(updated, "Transaction")[-2:]
    assert [tx.get("Pa") for tx in both] == [created_party.get("Nb")] * 2
    assert len(nodes(updated, "Party")) == 2
