"""Phase A/B archive compatibility and atomic-creation regression cases."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi.archive_support import archive_rows, date_archive_selection
from ncgrisbi.errors import MutationError, RecordNotFoundError
from ncgrisbi.mutation import apply_mutations
from ncgrisbi.parser import parse_document
from ncgrisbi.read import list_accounts_with_reports, list_accounts
from ncgrisbi.snapshot import build_account_snapshot
from ncgrisbi.validator import assert_valid_document
from test_phase_a_backend import fixture_bytes, TRANSACTION_TEMPLATE


def versioned(version="1.2.1"):
    source = fixture_bytes()
    if version == "2.0.0":
        source = source.replace(
            b'File_version="1.2.1" Grisbi_version="1.2.2"',
            b'File_version="2.0.0" Grisbi_version="3.0.4"',
        )
    return source


def archived_source(version="1.2.1"):
    raw = versioned(version)
    raw = raw.replace(b'Nb="1" Id="(null)" Dt="01/01/2026"', b'Nb="1" Id="(null)" Dt="01/01/2026"')
    # The first transaction belongs to a pre-existing archive.
    raw = raw.replace(b'Ma="1" Ar="0"', b'Ma="1" Ar="3"', 1)
    return raw.replace(
        b"</Grisbi>",
        b'<Archive Nb="3" Na="January" Bdte="01/01/2026" Edte="01/03/2026" Fye="0" Rep="(null)" />\n</Grisbi>',
    )


@pytest.mark.parametrize("version", ["1.2.1", "2.0.0"])
def test_existing_archives_listed_and_normal_snapshot_omits_their_rows(version):
    doc = parse_document(archived_source(version))
    assert_valid_document(doc)
    accounts = list_accounts_with_reports(doc)
    assert len(accounts["archives"]) == 1
    archive = accounts["archives"][0]
    assert archive["id"] == "3"
    assert archive["name"] == "January"
    assert archive["accounts"]["1"] == {"count": 1, "amount": "-10.00"}
    assert len(accounts["accounts"]) == 2

    normal = build_account_snapshot(doc, "1")
    assert len(normal["T"]) == 0
    assert normal["a"][8] == "-10.00"
    assert normal["a"][9] == "-10.00"
    archived = build_account_snapshot(doc, "1", "3")
    assert len(archived["T"]) == 1
    assert archived["T"][0][-1] == 1
    assert archived["T"][0][0] == "1"
    assert archived["a"][8] == "-10.00"
    with pytest.raises(RecordNotFoundError):
        build_account_snapshot(doc, "1", "99")


@pytest.mark.parametrize("version", ["1.2.1", "2.0.0"])
def test_archive_mutation_is_one_atomic_write_and_keeps_totals(version):
    original = versioned(version)
    before = list_accounts(parse_document(original))
    output = apply_mutations(original, [{
        "type": "createArchive", "name": "January 2026",
        "startDate": "01/01/2026", "endDate": "01/02/2026",
    }])
    doc = parse_document(output.raw_bytes)
    assert_valid_document(doc)
    archives = doc.root.findall("Archive")
    assert len(archives) == 1
    assert archives[0].attrib == {
        "Nb": "1", "Na": "January 2026",
        "Bdte": "01/01/2026", "Edte": "01/02/2026",
        "Fye": "0", "Rep": "(null)",
    }
    tx = doc.root.findall("Transaction")
    assert [item.get("Ar") for item in tx] == ["1", "1"]
    assert list_accounts(doc) == before
    assert build_account_snapshot(doc, "1")["T"] == []
    assert build_account_snapshot(doc, "2")["T"] == []
    assert len(output.outcomes) == 1
    assert output.outcomes[0]["count"] == 2

    for operation in [
        {"type": "deleteTransaction", "transactionId": "1"},
        {"type": "updateTransaction", "transactionId": "1",
         "changes": {"note": "Must not change"}},
        {"type": "setTransactionMarks", "marks": [["1", 0]]},
    ]:
        with pytest.raises(MutationError, match="Archived transactions are read-only"):
            apply_mutations(output.raw_bytes, [operation])

    # Unrelated subsequent edits must not rewrite the archive and its members.
    extra = apply_mutations(output.raw_bytes, [{"type": "createParty", "name": "New party"}])
    after = parse_document(extra.raw_bytes)
    assert after.root.find("Archive").attrib == archives[0].attrib
    assert [item.get("Ar") for item in after.root.findall("Transaction")] == ["1", "1"]


def test_range_and_existing_overlap_rejected():
    doc = parse_document(archived_source())
    with pytest.raises(MutationError, match="overlaps"):
        date_archive_selection(doc.root, "01/02/2026", "01/04/2026")
    with pytest.raises(MutationError, match="after"):
        date_archive_selection(doc.root, "02/01/2026", "01/01/2026")
    with pytest.raises(MutationError, match="No unarchived"):
        date_archive_selection(doc.root, "06/01/2026", "06/30/2026")


def test_transfer_selection_includes_counterpart_outside_date_range():
    original = versioned()
    # Transactions 1 and 2 form a reciprocal transfer across accounts.
    linked = original.replace(b'Trt="0" Mo="0"', b'Trt="2" Mo="0"', 1)
    linked = linked.replace(b'Trt="0" Mo="0"', b'Trt="1" Mo="0"', 1)
    doc = parse_document(linked)
    selection = date_archive_selection(doc.root, "01/01/2026", "01/01/2026")
    assert selection["transactionIds"] == ["1", "2"]
    output = apply_mutations(linked, [{
        "type": "createArchive", "name": "First day",
        "startDate": "01/01/2026", "endDate": "01/01/2026",
    }])
    assert [tx.get("Ar") for tx in parse_document(output.raw_bytes).root.findall("Transaction")] == ["1", "1"]


def test_split_parent_and_all_children_are_archived_together():
    original = versioned()
    # Add a second child, all in the same account.
    extra = TRANSACTION_TEMPLATE.format(
        account="1", number="3", amount="-2.00", note="child",
        payment="1", marked="0",
    ).replace('Dt="01/03/2026"', 'Dt="02/03/2026"').replace(
        'Trt="0" Mo="0"', 'Trt="0" Mo="1"'
    )
    original = original.replace(b'<Party Nb=', extra.encode() + b'\n<Party Nb=', 1)
    original = original.replace(b'Br="0" No="current-account"', b'Br="1" No="current-account"', 1)
    selection = date_archive_selection(parse_document(original).root, "01/01/2026", "01/01/2026")
    assert selection["transactionIds"] == ["1", "3"]


def test_archive_preview_and_creation_reject_already_archived_linked_transactions():
    raw = archived_source()
    with pytest.raises(MutationError, match="overlaps"):
        date_archive_selection(parse_document(raw).root, "01/01/2026", "01/01/2026")


def test_large_archive_does_not_require_one_mutation_per_transaction():
    source = versioned()
    template = TRANSACTION_TEMPLATE
    extras = []
    for number in range(3, 1105):
        extras.append(template.format(
            account="1", number=number, amount="-1.00",
            note="bulk", payment="1", marked="0",
        ).replace(f'Dt="01/0{number}/2026"', 'Dt="01/01/2026"'))
    source = source.replace(b'<Party Nb=', ("\n".join(extras) + "\n<Party Nb=").encode(), 1)
    result = apply_mutations(source, [{
        "type": "createArchive", "name": "Bulk",
        "startDate": "01/01/2026", "endDate": "01/02/2026",
    }])
    assert result.outcomes[0]["count"] == 1104
    assert len(parse_document(result.raw_bytes).root.findall("Archive")) == 1
