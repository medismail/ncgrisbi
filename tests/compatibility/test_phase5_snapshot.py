from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi.parser import parse_document
from ncgrisbi.phase5_protocol import execute_request
from ncgrisbi.protocol import PROTOCOL_VERSION
from ncgrisbi.snapshot import TX_TRANSFER, build_account_snapshot

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-real.gsb"


def test_compact_snapshot_uses_real_grisbi_ids_and_preferences() -> None:
    snapshot = build_account_snapshot(parse_document(FIXTURE.read_bytes()), "1")

    assert snapshot["v"] == 2
    assert snapshot["a"][0] == "1"
    assert snapshot["a"][1] == "Compte LCL"
    assert snapshot["a"][5] == "EUR"
    assert snapshot["a"][8] == "-52.00"
    transaction = snapshot["T"][0]
    assert transaction[0] == "1"
    assert transaction[4:8] == ["1", "1", "7", "3"]
    assert transaction[12] is None
    assert snapshot["H"]
    assert snapshot["U"][0] == 3
    assert snapshot["U"][1:3] == [0, 0]
    assert snapshot["U"][3].startswith("18-1-3-")
    assert snapshot["W"] == []


def test_real_reciprocal_transfer_is_editable() -> None:
    snapshot = build_account_snapshot(parse_document(FIXTURE.read_bytes()), "1")
    transfer = next(item for item in snapshot["T"] if item[0] == "3")
    assert transfer[16] & TX_TRANSFER
    assert transfer[17] == "2"
    assert transfer[18] == "7"


def test_phase5_protocol_returns_real_compact_json_snapshot() -> None:
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
    assert decoded["v"] == 2
    assert len(decoded["T"]) == 3
    assert decoded["U"][0] == 3
