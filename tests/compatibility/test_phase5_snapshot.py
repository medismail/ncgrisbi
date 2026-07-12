from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi.parser import parse_document
from ncgrisbi.phase5_protocol import execute_request
from ncgrisbi.protocol import PROTOCOL_VERSION
from ncgrisbi.snapshot import build_account_snapshot

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"


def test_snapshot_exposes_typed_ids_and_real_bank_reference() -> None:
    snapshot = build_account_snapshot(parse_document(FIXTURE.read_bytes()), "1")

    assert snapshot["account"]["id"] == "1"
    assert snapshot["account"]["totalAmount"] == "957.50"
    assert snapshot["account"]["currency"]["code"] == "EUR"
    transaction = snapshot["transactions"][0]
    assert transaction["id"] == "10"
    assert transaction["partyId"] == "1"
    assert transaction["categoryId"] == "1"
    assert transaction["subcategoryId"] == "1"
    assert transaction["paymentMethodId"] == "1"
    assert transaction["bankReference"] == "statement-10"
    assert transaction["protected"] is False


def test_snapshot_marks_transfer_and_split_fields_read_only() -> None:
    root = ET.fromstring(
        """<Grisbi>
        <Currency Nb="1" Na="Euro" Co="€" Ico="EUR" Fl="2" />
        <Account Name="Current" Number="1" Kind="0" Currency="1" />
        <Transaction Ac="1" Nb="10" Dt="07/01/2026" Dv="(null)" Cu="1" Am="1.00" Pa="0" Ca="0" Sca="0" Br="7" No="(null)" Pn="0" Pc="(null)" Ma="0" Vo="(null)" Ba="(null)" Trt="11" Mo="12" />
        </Grisbi>"""
    )
    snapshot = build_account_snapshot(SimpleNamespace(root=root), "1")
    transaction = snapshot["transactions"][0]
    assert transaction["protected"] is True
    assert transaction["protectionReasons"] == [
        "breakdown",
        "transfer",
        "split-child",
    ]


def test_phase5_protocol_returns_json_snapshot_payload() -> None:
    header, payload = execute_request(
        {
            "version": PROTOCOL_VERSION,
            "command": "accountSnapshot",
            "requestId": "snapshot-1",
            "accountId": "1",
        },
        FIXTURE.read_bytes(),
        None,
    )
    decoded = json.loads(payload.decode("utf-8"))
    assert header["ok"] is True
    assert header["changed"] is False
    assert header["contentType"] == "application/json"
    assert decoded["account"]["name"] == "Current account"
    assert len(decoded["transactions"]) == 2
