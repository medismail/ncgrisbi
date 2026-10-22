from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal

LIB = Path(__file__).resolve().parents[2] / "lib" / "bin"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import pytest

from ncgrisbi.errors import MutationError
from ncgrisbi.parser import parse_document
from ncgrisbi.read import list_accounts_with_reports
from ncgrisbi.report_engine import _period, report_snapshot
from ncgrisbi.worker import execute_request

from test_phase_a_backend import fixture_bytes


REPORT = (
    '<Report Nb="3" Name="Revenus et dépenses du 3 derniers mois" '
    'General_sort_type="1/-/2/-/3/-/4/-/5/-/6" Date_kind="10" '
    'Currency_general="1" Categ_currency="1" '
    'Categ_use="1" Categ_show_sub_categ="1" '
    'Categ_show_without_sub_categ="1" Show_split_amounts="1" '
    'Show_exclude_split_child="0" Transfer_kind="2" '
    'Account_use_selection="0" />'
)


def tx(number: int, amount: str, category: int, subcategory: int = 0,
       *, month: int = 10, day: int = 4, account: int = 1,
       transfer: int = 0, split_parent: int = 0, split_child: int = 0) -> str:
    payment = 2 if account == 2 else 1
    return (
        f'<Transaction Ac="{account}" Nb="{number}" Id="(null)" '
        f'Dt="{month:02d}/{day:02d}/2026" Dv="(null)" Cu="1" Am="{amount}" '
        f'Exb="0" Exr="0.00" Exf="0.00" Pa="1" Ca="{category}" '
        f'Sca="{subcategory}" Br="{split_parent}" No="(null)" Pn="{payment}" '
        f'Pc="(null)" Ma="0" Ar="0" Au="0" Re="0" Fi="0" Bu="0" '
        f'Sbu="0" Vo="(null)" Ba="(null)" Trt="{transfer}" Mo="{split_child}" />'
    )


def example_payload() -> bytes:
    extra = "\n".join([
        '<Category Nb="2" Na="Salary" Kd="0" />',
        '<Sub_category Nbc="2" Nb="1" Na="Main salary" />',
        tx(3, "-5.00", 1),
        tx(4, "100.00", 2, 1),
        tx(5, "25.00", 2),
        tx(6, "15.00", 0),
        tx(7, "-7.00", 0),
        tx(8, "-10.00", 0, transfer=9),
        tx(9, "10.00", 0, account=2, transfer=8),
        tx(10, "-30.00", 1, split_parent=1),
        tx(11, "-12.00", 1, 1, split_child=10),
        tx(12, "-18.00", 1, 0, split_child=10),
        REPORT,
    ])
    base = fixture_bytes().replace(b'01/01/2026', b'10/01/2026')
    base = base.replace(b'01/02/2026', b'10/02/2026')
    return base.replace(b"</Grisbi>", extra.encode() + b"\n</Grisbi>")


def test_open_file_returns_accounts_and_report_metadata_together() -> None:
    payload = example_payload()
    doc = parse_document(payload)
    result = list_accounts_with_reports(doc)
    assert result["reports"] == [
        {"id": "3", "name": "Revenus et dépenses du 3 derniers mois"}
    ]
    assert len(result["accounts"]) == 2
    header, encoded = execute_request(
        {"version": 1, "requestId": "reports-list", "command": "listAccounts"},
        payload,
        None,
    )
    assert header["ok"] is True
    assert json.loads(encoded)["reports"] == result["reports"]


def test_report_groups_totals_counts_and_transaction_references() -> None:
    result = report_snapshot(parse_document(example_payload()), "3", date(2026, 10, 21))
    assert result["period"] == {"from": "2026-07-21", "to": "2026-10-21"}
    assert result["currency"] == "EUR"
    assert result["income"]["count"] == 3
    assert Decimal(result["income"]["total"]) == Decimal("140")
    salary = result["income"]["categories"][0]
    assert salary["name"] == "Salary"
    assert salary["count"] == 2
    assert Decimal(salary["amount"]) == Decimal("125")
    assert [child["name"] for child in salary["subcategories"]] == [
        "Main salary", "No subcategory"
    ]
    assert [child["count"] for child in salary["subcategories"]] == [1, 1]
    assert result["income"]["uncategorized"]["count"] == 1
    food = result["expenses"]["categories"][0]
    assert food["name"] == "Food"
    assert food["count"] == 5
    assert Decimal(food["amount"]) == Decimal("65")
    assert [child["name"] for child in food["subcategories"]] == [
        "Groceries", "No subcategory"
    ]
    assert [child["count"] for child in food["subcategories"]] == [3, 2]
    assert result["expenses"]["count"] == 6
    assert Decimal(result["expenses"]["total"]) == Decimal("72")
    assert Decimal(result["difference"]) == Decimal("68")
    assert len(result["transactions"]) == 9  # excludes parent split and transfers
    referenced = []
    for side in ("income", "expenses"):
        section = result[side]
        for category in section["categories"]:
            for subcategory in category["subcategories"]:
                referenced.extend(subcategory["transactions"])
        if section["uncategorized"]:
            referenced.extend(section["uncategorized"]["transactions"])
    assert sorted(referenced) == list(range(len(result["transactions"])))
    assert {row["id"] for row in result["transactions"]}.isdisjoint({"8", "9", "10"})


def test_rolling_three_month_period_clamps_end_of_month() -> None:
    report = parse_document(example_payload()).root.find("Report")
    assert _period(report, date(2026, 5, 31)) == (
        date(2026, 2, 28), date(2026, 5, 31)
    )


def test_unsupported_filters_fail_instead_of_returning_wrong_totals() -> None:
    bad = example_payload().replace(b'Categ_use="1"', b'Categ_use="0"')
    with pytest.raises(MutationError, match="category"):
        report_snapshot(parse_document(bad), "3", date(2026, 10, 21))


def test_currency_mismatch_is_not_silently_added_to_report_total() -> None:
    # Transaction currency is not convertible without exact Grisbi exchange semantics.
    bad = example_payload().replace(
        b'Nb="4" Id="(null)" Dt="10/04/2026" Dv="(null)" Cu="1"',
        b'Nb="4" Id="(null)" Dt="10/04/2026" Dv="(null)" Cu="2"'
    )
    with pytest.raises(MutationError, match="currency conversion"):
        report_snapshot(parse_document(bad), "3", date(2026, 10, 21))
