from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .model import ElementSpan, GsbDocument


@dataclass(frozen=True)
class IndexedRecord:
    element: ET.Element
    span: ElementSpan

    @property
    def attributes(self) -> Dict[str, str]:
        return dict(self.element.attrib)


@dataclass(frozen=True)
class GsbIndex:
    accounts: Dict[str, IndexedRecord]
    currencies: Dict[str, IndexedRecord]
    payments: Dict[str, IndexedRecord]
    transactions: Dict[str, IndexedRecord]
    parties: Dict[str, IndexedRecord]
    categories: Dict[str, IndexedRecord]
    subcategories: Dict[Tuple[str, str], IndexedRecord]

    @classmethod
    def build(cls, document: GsbDocument) -> "GsbIndex":
        accounts: Dict[str, IndexedRecord] = {}
        currencies: Dict[str, IndexedRecord] = {}
        payments: Dict[str, IndexedRecord] = {}
        transactions: Dict[str, IndexedRecord] = {}
        parties: Dict[str, IndexedRecord] = {}
        categories: Dict[str, IndexedRecord] = {}
        subcategories: Dict[Tuple[str, str], IndexedRecord] = {}

        for element, span in zip(list(document.root), document.spans):
            record = IndexedRecord(element=element, span=span)
            if element.tag == "Account":
                key = element.get("Number")
                if key is not None:
                    accounts[key] = record
            elif element.tag == "Currency":
                key = element.get("Nb")
                if key is not None:
                    currencies[key] = record
            elif element.tag == "Payment":
                # Payment.Number is globally unique in Grisbi. Account is a
                # selection/filtering property, not part of the identifier.
                key = element.get("Number")
                if key is not None:
                    payments[key] = record
            elif element.tag == "Transaction":
                key = element.get("Nb")
                if key is not None:
                    transactions[key] = record
            elif element.tag == "Party":
                key = element.get("Nb")
                if key is not None:
                    parties[key] = record
            elif element.tag == "Category":
                key = element.get("Nb")
                if key is not None:
                    categories[key] = record
            elif element.tag == "Sub_category":
                category = element.get("Nbc")
                number = element.get("Nb")
                if category is not None and number is not None:
                    subcategories[(category, number)] = record

        return cls(
            accounts=accounts,
            currencies=currencies,
            payments=payments,
            transactions=transactions,
            parties=parties,
            categories=categories,
            subcategories=subcategories,
        )

    @staticmethod
    def _next_numeric(values) -> str:
        maximum = 0
        for value in values:
            try:
                maximum = max(maximum, int(value))
            except (TypeError, ValueError):
                continue
        return str(maximum + 1)

    def next_transaction_id(self) -> str:
        return self._next_numeric(self.transactions)

    def next_party_id(self) -> str:
        return self._next_numeric(self.parties)

    def next_category_id(self) -> str:
        return self._next_numeric(self.categories)

    def next_subcategory_id(self, category_id: str) -> str:
        return self._next_numeric(
            number for parent, number in self.subcategories if parent == category_id
        )

    def last_subcategory_span(self, category_id: str) -> Optional[ElementSpan]:
        matches = [
            record.span
            for (parent, _), record in self.subcategories.items()
            if parent == category_id
        ]
        if matches:
            return max(matches, key=lambda span: span.start)
        category = self.categories.get(category_id)
        return category.span if category is not None else None
