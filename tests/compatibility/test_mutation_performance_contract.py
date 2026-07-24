from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib" / "bin"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import ncgrisbi.mutation as mutation


XML = """<Grisbi>
<Currency Nb="1" />
<Account Number="1" Currency="1" />
<Payment Number="1" Account="1" />
<Party Nb="1" />
<Category Nb="1" />
<Sub_category Nbc="1" Nb="1" />
<Transaction Ac="1" Nb="1" />
</Grisbi>"""


class CountingRoot:
    def __init__(self) -> None:
        self.element = ET.fromstring(XML)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return iter(self.element)


def test_mutation_session_indexes_root_and_spans_once(monkeypatch) -> None:
    root = CountingRoot()
    children = list(root.element)
    document = SimpleNamespace(
        root=root,
        spans=[object() for _element in children],
    )
    monkeypatch.setattr(mutation, "assert_valid_document", lambda _document: None)

    session = mutation.MutationSession(document)

    assert root.iterations == 1
    assert set(session.accounts) == {"1"}
    assert set(session.currencies) == {"1"}
    assert set(session.payments) == {"1"}
    assert set(session.parties) == {"1"}
    assert set(session.categories) == {"1"}
    assert set(session.subcategories) == {("1", "1")}
    assert set(session.transactions) == {"1"}
