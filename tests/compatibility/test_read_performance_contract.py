from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib" / "bin"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from ncgrisbi.read import list_accounts, list_parties, list_transactions


XML = """<Grisbi>
<Currency Nb="1" Ico="EUR" />
<Account Number="1" Name="Main" Kind="0" Currency="1" Bank="0" Closed_account="0" />
<Payment Number="1" Name="Card" Account="1" />
<Party Nb="1" Na="Shop" />
<Category Nb="1" Na="Food" Kd="1" />
<Sub_category Nbc="1" Nb="1" Na="Groceries" />
<Transaction Ac="1" Nb="1" Dt="01/01/2026" Cu="1" Am="-10.00" Pa="1" Ca="1" Sca="1" Br="0" No="Test" Pn="1" Pc="(null)" Ma="1" Trt="0" />
</Grisbi>"""


class CountingRoot:
    def __init__(self) -> None:
        self.element = ET.fromstring(XML)
        self.iterations = 0
        self.findall_calls = 0

    def __iter__(self):
        self.iterations += 1
        return iter(self.element)

    def findall(self, _path):
        self.findall_calls += 1
        raise AssertionError("transaction-heavy reads must use the one-pass index")


def _document():
    root = CountingRoot()
    return SimpleNamespace(root=root), root


def test_account_read_indexes_direct_children_once() -> None:
    document, root = _document()
    accounts = list_accounts(document)
    assert accounts[0]["total"]["total_amount"] == -10.0
    assert root.iterations == 1
    assert root.findall_calls == 0


def test_party_read_indexes_direct_children_once() -> None:
    document, root = _document()
    parties = list_parties(document)
    assert parties[0]["last_amount"] == -10.0
    assert root.iterations == 1
    assert root.findall_calls == 0


def test_transaction_read_indexes_direct_children_once() -> None:
    document, root = _document()
    result = list_transactions(document, "1")
    assert result["total_amount"] == -10.0
    assert result["transactions"][0]["TxNb"] == "1"
    assert root.iterations == 1
    assert root.findall_calls == 0
