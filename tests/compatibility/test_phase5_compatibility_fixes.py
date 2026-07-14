from __future__ import annotations

import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi.parser import parse_document
from ncgrisbi.snapshot import build_account_snapshot
from ncgrisbi.transfers import create_transfer, delete_transfer, update_transfer
from ncgrisbi.validator import assert_valid_document


def _transaction(
    account: str,
    number: str,
    amount: str,
    payment: str = "1",
    note: str = "N",
) -> str:
    return (
        '\t<Transaction Ac="%s" Nb="%s" Id="(null)" Dt="07/01/2026" '
        'Dv="(null)" Cu="1" Am="%s" Exb="0" Exr="0.00" Exf="0.00" '
        'Pa="1" Ca="1" Sca="1" Br="0" No="%s" Pn="%s" Pc="(null)" '
        'Ma="0" Ar="0" Au="0" Re="0" Fi="0" Bu="0" Sbu="0" '
        'Vo="(null)" Ba="(null)" Trt="0" Mo="0" />\n'
        % (account, number, amount, note, payment)
    )


def _fixture(extra_transactions: str = "") -> bytes:
    return (
        '<?xml version="1.0"?>\n<Grisbi>\n'
        '\t<General File_version="1.2.1" Grisbi_version="1.2.2" Crypt_file="0" Archive_file="0" />\n'
        '\t<Currency Nb="1" Na="Euro" Co="€" Ico="EUR" Fl="2" />\n'
        '\t<Account Name="Current" Id="a1" Number="1" Owner="U" Kind="0" Currency="1" Path_icon="(null)" Bank="0" Default_debit_method="1" Default_credit_method="2" />\n'
        '\t<Account Name="Savings" Id="a2" Number="2" Owner="U" Kind="0" Currency="1" Path_icon="(null)" Bank="0" Default_debit_method="3" Default_credit_method="4" />\n'
        '\t<Payment Number="1" Name="Card" Sign="1" Show_entry="0" Automatic_number="0" Current_number="(null)" Account="1" />\n'
        '\t<Payment Number="2" Name="Deposit" Sign="2" Show_entry="0" Automatic_number="0" Current_number="(null)" Account="1" />\n'
        '\t<Payment Number="3" Name="Transfer out" Sign="1" Show_entry="0" Automatic_number="0" Current_number="(null)" Account="2" />\n'
        '\t<Payment Number="4" Name="Transfer in" Sign="2" Show_entry="0" Automatic_number="0" Current_number="(null)" Account="2" />\n'
        + _transaction("1", "10", "-5.00")
        + extra_transactions
        + '\t<Party Nb="1" Na="Shop" Txt="(null)" Search="(null)" IgnCase="0" UseRegex="0" />\n'
        '\t<Category Nb="1" Na="Food" Kd="1" />\n'
        '\t<Sub_category Nbc="1" Nb="1" Na="Groceries" />\n'
        '</Grisbi>\n'
    ).encode("utf-8")


def test_existing_payment_is_validated_by_global_number() -> None:
    raw = _fixture().replace(b'Pn="1" Pc=', b'Pn="3" Pc=', 1)
    assert_valid_document(parse_document(raw))


def test_reciprocal_transfer_create_update_delete() -> None:
    result = create_transfer(
        parse_document(_fixture()),
        {
            "type": "createTransfer",
            "accountId": "1",
            "targetAccountId": "2",
            "date": "07/10/2026",
            "amount": "-20.00",
            "partyName": "Landlord",
            "createMissing": True,
            "paymentMethodId": "1",
            "targetPaymentMethodId": "4",
            "note": "Rent",
        },
    )
    root = ET.fromstring(result.raw_bytes)
    transactions = {
        element.get("Nb"): element for element in root.findall("Transaction")
    }
    source = transactions["11"]
    counterpart = transactions["12"]
    assert source.get("Trt") == "12"
    assert counterpart.get("Trt") == "11"
    assert source.get("Am") == "-20.00"
    assert counterpart.get("Am") == "20.00"
    assert counterpart.get("Ac") == "2"
    assert counterpart.get("Pn") == "4"

    updated = update_transfer(
        parse_document(result.raw_bytes),
        {
            "type": "updateTransfer",
            "transactionId": "11",
            "changes": {
                "amount": "-25.50",
                "date": "07/11/2026",
                "note": "Rent corrected",
            },
        },
    )
    root = ET.fromstring(updated.raw_bytes)
    transactions = {
        element.get("Nb"): element for element in root.findall("Transaction")
    }
    assert transactions["11"].get("Am") == "-25.50"
    assert transactions["12"].get("Am") == "25.50"
    assert transactions["11"].get("Dt") == "07/11/2026"
    assert transactions["12"].get("Dt") == "07/11/2026"
    assert transactions["11"].get("No") == "Rent corrected"
    assert transactions["12"].get("No") == "Rent corrected"

    deleted = delete_transfer(
        parse_document(updated.raw_bytes),
        {"type": "deleteTransfer", "transactionId": "11"},
    )
    remaining = {
        element.get("Nb")
        for element in ET.fromstring(deleted.raw_bytes).findall("Transaction")
    }
    assert remaining == {"10"}


def test_compact_snapshot_is_under_35_percent_of_verbose_shape() -> None:
    extra = "".join(
        _transaction(
            "1",
            str(number),
            "-1.00",
            note="Repeated merchant transaction",
        )
        for number in range(20, 1020)
    )
    compact = build_account_snapshot(parse_document(_fixture(extra)), "1")
    compact_bytes = json.dumps(
        compact,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    verbose = {
        "account": {
            "id": "1",
            "name": "Current",
            "currency": {
                "id": "1",
                "name": "Euro",
                "code": "EUR",
                "symbol": "€",
                "precision": 2,
            },
        },
        "parties": [{"id": "1", "name": "Shop"}],
        "categories": [
            {
                "id": "1",
                "name": "Food",
                "kind": 1,
                "subcategories": [{"id": "1", "name": "Groceries"}],
            }
        ],
        "paymentMethods": [{"id": "1", "name": "Card", "sign": 1}],
        "transactions": [],
    }
    for transaction in compact["T"]:
        verbose["transactions"].append(
            {
                "id": transaction[0],
                "date": transaction[1],
                "valueDate": transaction[2],
                "amount": transaction[3],
                "currencyId": "1",
                "partyId": "1",
                "partyName": "Shop",
                "categoryId": "1",
                "categoryName": "Food",
                "subcategoryId": "1",
                "subcategoryName": "Groceries",
                "paymentMethodId": "1",
                "paymentMethodName": "Card",
                "note": transaction[8],
                "paymentReference": None,
                "marked": 0,
                "voucher": None,
                "bankReference": None,
                "protected": False,
                "protectionReasons": [],
                "transferTransactionId": None,
                "splitMotherId": None,
            }
        )
    verbose_bytes = json.dumps(
        verbose,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    assert len(compact_bytes) < len(verbose_bytes) * 0.35
