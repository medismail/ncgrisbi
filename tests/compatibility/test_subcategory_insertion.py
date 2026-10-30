"""Preserve physical Grisbi category grouping when inserting subcategories."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi.mutation import apply_mutations
from ncgrisbi.parser import parse_document
from ncgrisbi.validator import assert_valid_document

from test_phase_a_backend import fixture_bytes


def source(version: str, *, include_second_subcategory: bool = True) -> bytes:
    original = fixture_bytes()
    if version == "2.0.0":
        original = original.replace(
            b'File_version="1.2.1" Grisbi_version="1.2.2"',
            b'File_version="2.0.0" Grisbi_version="3.0.4"',
        )
    second = (
        b'<Sub_category Nbc="2" Nb="1" Na="Fuel" />\n'
        if include_second_subcategory else b""
    )
    return original.replace(
        b'</Grisbi>',
        b'<Category Nb="2" Na="Transport" Kd="1" />\n'
        + second
        + b'</Grisbi>',
    )


def category_records(raw_bytes: bytes):
    document = parse_document(raw_bytes)
    assert_valid_document(document)
    return [
        (element.tag, element.get("Nb"), element.get("Nbc"), element.get("Na"))
        for element in document.root
        if element.tag in ("Category", "Sub_category")
    ]


@pytest.mark.parametrize("version", ["1.2.1", "2.0.0"])
def test_new_subcategory_stays_under_existing_parent(version):
    original = source(version)
    result = apply_mutations(original, [
        {"type": "createSubcategory", "categoryId": "1", "name": "Restaurants"},
    ])
    records = category_records(result.raw_bytes)
    assert records == [
        ("Category", "1", None, "Food"),
        ("Sub_category", "1", "1", "Groceries"),
        ("Sub_category", "2", "1", "Restaurants"),
        ("Category", "2", None, "Transport"),
        ("Sub_category", "1", "2", "Fuel"),
    ]
    # Lossless writer: all original bytes remain untouched except the insert.
    added_line = next(
        line for line in result.raw_bytes.splitlines(keepends=True)
        if b'Na="Restaurants"' in line
    )
    assert result.raw_bytes.replace(added_line, b"", 1) == original


@pytest.mark.parametrize("version", ["1.2.1", "2.0.0"])
def test_first_subcategory_is_inserted_after_empty_parent(version):
    original = source(version, include_second_subcategory=False)
    original = original.replace(
        b'</Grisbi>',
        b'<Category Nb="3" Na="Other" Kd="1" />\n</Grisbi>',
    )
    result = apply_mutations(original, [
        {"type": "createSubcategory", "categoryId": "2", "name": "Train"},
    ])
    assert category_records(result.raw_bytes) == [
        ("Category", "1", None, "Food"),
        ("Sub_category", "1", "1", "Groceries"),
        ("Category", "2", None, "Transport"),
        ("Sub_category", "1", "2", "Train"),
        ("Category", "3", None, "Other"),
    ]


@pytest.mark.parametrize("version", ["1.2.1", "2.0.0"])
def test_batch_groups_existing_and_new_parents_and_preserves_child_order(version):
    original = source(version)
    result = apply_mutations(original, [
        {"type": "createCategory", "name": "Holidays", "kind": 1},  # 3
        {"type": "createCategory", "name": "Housing", "kind": 1},   # 4
        {"type": "createSubcategory", "categoryId": "2", "name": "Train"},
        {"type": "createSubcategory", "categoryId": "4", "name": "Rent"},
        {"type": "createSubcategory", "categoryId": "3", "name": "Flights"},
        {"type": "createSubcategory", "categoryId": "1", "name": "Restaurants"},
        {"type": "createSubcategory", "categoryId": "3", "name": "Hotels"},
        {"type": "createSubcategory", "categoryId": "2", "name": "Bus"},
        {"type": "createSubcategory", "categoryId": "4", "name": "Repairs"},
    ])
    assert category_records(result.raw_bytes) == [
        ("Category", "1", None, "Food"),
        ("Sub_category", "1", "1", "Groceries"),
        ("Sub_category", "2", "1", "Restaurants"),
        ("Category", "2", None, "Transport"),
        ("Sub_category", "1", "2", "Fuel"),
        ("Sub_category", "2", "2", "Train"),
        ("Sub_category", "3", "2", "Bus"),
        ("Category", "3", None, "Holidays"),
        ("Sub_category", "1", "3", "Flights"),
        ("Sub_category", "2", "3", "Hotels"),
        ("Category", "4", None, "Housing"),
        ("Sub_category", "1", "4", "Rent"),
        ("Sub_category", "2", "4", "Repairs"),
    ]


@pytest.mark.parametrize("version", ["1.2.1", "2.0.0"])
def test_name_based_transaction_subcategory_creation_uses_parent_anchor(version):
    original = source(version)
    result = apply_mutations(original, [{
        "type": "createTransaction", "accountId": "1", "date": "02/01/2026",
        "amount": "-7.00", "paymentMethodId": "1",
        "categoryName": "Food", "subcategoryName": "Takeaway",
        "createMissing": True,
    }])
    records = category_records(result.raw_bytes)
    assert records[2] == ("Sub_category", "2", "1", "Takeaway")
    assert records[3] == ("Category", "2", None, "Transport")


@pytest.mark.parametrize("version", ["1.2.1", "2.0.0"])
def test_new_category_and_subcategory_from_transaction_are_adjacent(version):
    original = source(version)
    result = apply_mutations(original, [{
        "type": "createTransaction", "accountId": "1", "date": "02/01/2026",
        "amount": "-7.00", "paymentMethodId": "1",
        "categoryName": "Travel", "subcategoryName": "Lodging",
        "createMissing": True,
    }])
    records = category_records(result.raw_bytes)
    assert records[-2:] == [
        ("Category", "3", None, "Travel"),
        ("Sub_category", "1", "3", "Lodging"),
    ]
