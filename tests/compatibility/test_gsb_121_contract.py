from __future__ import annotations

import importlib.util
import re
import sys
import types
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "compatibility" / "fixtures"
EXPECTED_DIR = ROOT / "tests" / "compatibility" / "expected"
BASIC_FIXTURE = FIXTURE_DIR / "grisbi-1.2.2-basic.gsb"

EXPECTED_SECTION_ORDER = [
    "General",
    "Currency",
    "Account",
    "Account",
    "Payment",
    "Payment",
    "Transaction",
    "Transaction",
    "Transaction",
    "Party",
    "Party",
    "Category",
    "Sub_category",
    "Category",
    "Sub_category",
    "Bank",
]

EXPECTED_ATTRIBUTE_ORDER = {
    "Transaction": [
        "Ac", "Nb", "Id", "Dt", "Dv", "Cu", "Am", "Exb", "Exr", "Exf",
        "Pa", "Ca", "Sca", "Br", "No", "Pn", "Pc", "Ma", "Ar", "Au",
        "Re", "Fi", "Bu", "Sbu", "Vo", "Ba", "Trt", "Mo",
    ],
    "Party": ["Nb", "Na", "Txt", "Search", "IgnCase", "UseRegex"],
    "Category": ["Nb", "Na", "Kd"],
    "Sub_category": ["Nbc", "Nb", "Na"],
}


def load_current_grisbi_module():
    """Load lib/bin/grisbi.py without requiring the encryption dependency.

    Phase 0 exercises only the XML parser and extractor. The encryption module is
    injected as an empty module because it is used only by the command-line path.
    """
    module_path = ROOT / "lib" / "bin" / "grisbi.py"
    module_name = "ncgrisbi_phase0_grisbi"
    sys.modules.setdefault("gsb_decode", types.ModuleType("gsb_decode"))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_fixture_text() -> str:
    return BASIC_FIXTURE.read_text(encoding="utf-8")


def first_line_for(tag: str) -> str:
    prefix = f"\t<{tag} "
    return next(line for line in read_fixture_text().splitlines() if line.startswith(prefix))


def attribute_names(xml_line: str) -> list[str]:
    return re.findall(r"\s([A-Za-z_][A-Za-z0-9_]*)=\"", xml_line)


def test_fixture_targets_grisbi_1_2_2_file_1_2_1() -> None:
    root = ET.fromstring(BASIC_FIXTURE.read_bytes())
    general = root.find("General")
    assert root.tag == "Grisbi"
    assert general is not None
    assert general.get("Grisbi_version") == "1.2.2"
    assert general.get("File_version") == "1.2.1"


def test_top_level_section_order_matches_the_1_2_2_writer_contract() -> None:
    root = ET.fromstring(BASIC_FIXTURE.read_bytes())
    assert [child.tag for child in root] == EXPECTED_SECTION_ORDER


def test_canonical_record_attribute_order() -> None:
    for tag, expected in EXPECTED_ATTRIBUTE_ORDER.items():
        assert attribute_names(first_line_for(tag)) == expected


def test_expected_canonical_records_are_present_byte_for_byte() -> None:
    fixture_lines = set(read_fixture_text().splitlines())
    for expected_path in sorted(EXPECTED_DIR.glob("*.xml")):
        expected_line = expected_path.read_text(encoding="utf-8").rstrip("\n")
        assert expected_line in fixture_lines, expected_path.name


def test_fixture_references_are_internally_consistent() -> None:
    root = ET.fromstring(BASIC_FIXTURE.read_bytes())
    accounts = {node.get("Number") for node in root.findall("Account")}
    currencies = {node.get("Nb") for node in root.findall("Currency")}
    parties = {node.get("Nb") for node in root.findall("Party")}
    categories = {node.get("Nb") for node in root.findall("Category")}
    subcategories = {
        (node.get("Nbc"), node.get("Nb")) for node in root.findall("Sub_category")
    }
    payments = {
        (node.get("Account"), node.get("Number")) for node in root.findall("Payment")
    }

    numbers: set[str] = set()
    for transaction in root.findall("Transaction"):
        number = transaction.get("Nb")
        assert number is not None and number not in numbers
        numbers.add(number)

        account = transaction.get("Ac")
        assert account in accounts
        assert transaction.get("Cu") in currencies
        assert transaction.get("Pa") == "0" or transaction.get("Pa") in parties
        assert transaction.get("Ca") == "0" or transaction.get("Ca") in categories
        assert transaction.get("Sca") == "0" or (
            transaction.get("Ca"), transaction.get("Sca")
        ) in subcategories
        assert (account, transaction.get("Pn")) in payments
        Decimal(transaction.get("Am", ""))


def test_current_reader_extracts_the_phase0_fixture() -> None:
    grisbi = load_current_grisbi_module()
    root = grisbi.parse_gsb_content(BASIC_FIXTURE.read_bytes())
    assert root is not None

    (
        accounts,
        parties,
        transactions,
        categories,
        subcategories,
        payments,
        account_totals,
        next_id,
    ) = grisbi.extract_data(root)

    assert set(accounts) == {"1", "2"}
    assert accounts["1"]["currency"] == "EUR"
    assert parties["1"]["name"] == "Electricity & Water"
    assert categories == {"1": "Housing", "2": "Income"}
    assert subcategories["1"] == [{"id": "1", "name": "Electricity"}]
    assert payments["1"]["account"] == "1"
    assert len(transactions) == 3
    assert account_totals["1"]["total_amount"] == Decimal("957.50")
    assert account_totals["2"]["total_amount"] == Decimal("250.00")
    assert next_id == "12"
