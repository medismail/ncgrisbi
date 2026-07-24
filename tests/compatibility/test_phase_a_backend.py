from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib" / "bin"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from ncgrisbi.formats import GSB_121_PROFILE, SupportLevel, supported_file_versions
from ncgrisbi.index import GsbIndex
from ncgrisbi.parser import parse_document
from ncgrisbi.snapshot_service import build_account_snapshot
from ncgrisbi.validator import assert_valid_document
from ncgrisbi.worker import execute_request
from ncgrisbi.writer import LosslessPatchWriter


TRANSACTION_TEMPLATE = (
    '<Transaction Ac="{account}" Nb="{number}" Id="(null)" '
    'Dt="01/0{number}/2026" Dv="(null)" Cu="1" Am="{amount}" '
    'Exb="0" Exr="0.00" Exf="0.00" Pa="1" Ca="1" Sca="1" '
    'Br="0" No="{note}" Pn="{payment}" Pc="(null)" Ma="{marked}" '
    'Ar="0" Au="0" Re="0" Fi="0" Bu="0" Sbu="0" '
    'Vo="(null)" Ba="(null)" Trt="0" Mo="0" />'
)


def fixture_bytes() -> bytes:
    transactions = "\n".join(
        [
            TRANSACTION_TEMPLATE.format(
                account="1",
                number="1",
                amount="-10.00",
                note="current-account",
                payment="1",
                marked="1",
            ),
            TRANSACTION_TEMPLATE.format(
                account="2",
                number="2",
                amount="-20.00",
                note="other-account",
                payment="2",
                marked="0",
            ),
        ]
    )
    return (
        '<?xml version="1.0"?>\n'
        '<Grisbi>\n'
        '<General File_version="1.2.1" Grisbi_version="1.2.2" />\n'
        '<Currency Nb="1" Na="Euro" Ico="EUR" Co="€" Fl="2" />\n'
        '<Account Number="1" Name="Main" Kind="0" Currency="1" Bank="0" '
        'Default_debit_method="1" Default_credit_method="1" '
        'Closed_account="0" Lines_per_transaction="1" Sorting_kind_column="" />\n'
        '<Account Number="2" Name="Other" Kind="0" Currency="1" Bank="0" '
        'Default_debit_method="2" Default_credit_method="2" '
        'Closed_account="0" Lines_per_transaction="1" Sorting_kind_column="" />\n'
        '<Payment Number="1" Name="Card" Sign="1" Show_entry="1" '
        'Automatic_number="0" Current_number="(null)" Account="1" />\n'
        '<Payment Number="2" Name="Card" Sign="1" Show_entry="1" '
        'Automatic_number="0" Current_number="(null)" Account="2" />\n'
        f'{transactions}\n'
        '<Party Nb="1" Na="Shop" Txt="(null)" Search="(null)" '
        'IgnCase="0" UseRegex="0" />\n'
        '<Category Nb="1" Na="Food" Kd="1" />\n'
        '<Sub_category Nbc="1" Nb="1" Na="Groceries" />\n'
        '</Grisbi>'
    ).encode("utf-8")


def test_profile_owns_the_121_schema_and_creation_defaults() -> None:
    assert supported_file_versions() == ("1.2.1",)
    assert GSB_121_PROFILE.support_level is SupportLevel.READ_WRITE
    assert GSB_121_PROFILE.attribute_order["Transaction"][0:3] == (
        "Ac",
        "Nb",
        "Id",
    )
    attributes = GSB_121_PROFILE.new_transaction_attributes(
        account_id="1",
        transaction_id="3",
        date="01/03/2026",
        value_date="(null)",
        currency_id="1",
        amount="-3.00",
        party_id="1",
        payment_id="1",
    )
    assert attributes["Exb"] == "0"
    assert attributes["Trt"] == "0"
    assert tuple(attributes) == GSB_121_PROFILE.attribute_order["Transaction"]


def test_parser_validator_writer_and_index_use_the_document_profile() -> None:
    document = parse_document(fixture_bytes())
    assert document.format_profile is GSB_121_PROFILE
    assert_valid_document(document)

    index = GsbIndex.build(document)
    assert set(index.payments) == {"1", "2"}

    transaction = document.find_span("Transaction", "Nb", "1")
    assert transaction is not None
    writer = LosslessPatchWriter(document)
    writer.replace_attribute(transaction, "Ma", "0")
    output = writer.render()
    changed = parse_document(output)
    assert changed.root.find("Transaction").get("Ma") == "0"
    assert changed.file_version == "1.2.1"


def test_snapshot_service_prefers_current_account_completion() -> None:
    document = parse_document(fixture_bytes())
    snapshot = build_account_snapshot(document, "1")
    history = {row[0]: row for row in snapshot["H"]}
    assert history["1"][1] == "1"
    assert history["1"][6] == "current-account"


def test_framed_worker_serves_all_read_models_from_one_document_pipeline() -> None:
    payload = fixture_bytes()
    base = {"version": 1, "requestId": "phase-a"}

    header, output = execute_request(
        {**base, "command": "listAccounts"},
        payload,
        password=None,
    )
    assert header["contentType"] == "application/json"
    accounts = json.loads(output)
    assert accounts[0]["id"] == "1"
    assert accounts[0]["total"]["total_amount"] == -10.0
    assert accounts[0]["total"]["total_marked_amount"] == -10.0

    _header, output = execute_request(
        {**base, "command": "listParties"},
        payload,
        password=None,
    )
    assert json.loads(output)[0]["name"] == "Shop"

    _header, output = execute_request(
        {**base, "command": "listCategories"},
        payload,
        password=None,
    )
    assert json.loads(output)[0]["subcategories"][0]["name"] == "Groceries"

    _header, output = execute_request(
        {**base, "command": "listTransactions", "accountId": "1"},
        payload,
        password=None,
    )
    transactions = json.loads(output)
    assert transactions["account_name"] == "Main"
    assert transactions["transactions"][0]["Note"] == "current-account"

    _header, output = execute_request(
        {**base, "command": "accountSnapshot", "accountId": "1"},
        payload,
        password=None,
    )
    assert json.loads(output)["a"][0] == "1"


def test_envelope_inspection_does_not_require_the_file_password() -> None:
    header, output = execute_request(
        {"version": 1, "requestId": "envelope", "command": "inspectEnvelope"},
        b"Grisbi encryption v2: test",
        password=None,
    )
    assert header["ok"] is True
    assert json.loads(output) == {"compressed": False, "encrypted": True}


def test_active_entrypoint_does_not_load_legacy_backend_generations() -> None:
    entrypoint = (LIB / "ncgrisbi_protocol.py").read_text(encoding="utf-8")
    worker = (LIB / "ncgrisbi" / "worker.py").read_text(encoding="utf-8")
    phase5_shim = (LIB / "ncgrisbi" / "phase5_protocol.py").read_text(
        encoding="utf-8"
    )
    process = (ROOT / "lib" / "Grisbi" / "GrisbiProcess.php").read_text(
        encoding="utf-8"
    )

    assert "from ncgrisbi.worker import main" in entrypoint
    assert "from .framing import" in worker
    assert "from .protocol import" not in worker
    assert "phase4_protocol" not in worker
    assert "compat_engine" not in worker
    assert "from .worker import" in phase5_shim
    assert "$this->legacyWrapperPath" not in process
    assert not (LIB / "ncgrisbi_legacy.py").exists()
    assert not (LIB / "grisbi.py").exists()
