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

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"


def test_compact_snapshot_has_ids_bank_reference_and_completion() -> None:
    snapshot = build_account_snapshot(parse_document(FIXTURE.read_bytes()), "1")

    assert snapshot["v"] == 2
    assert snapshot["a"][0] == "1"
    assert snapshot["a"][5] == "EUR"
    assert snapshot["a"][8] == "957.50"
    transaction = snapshot["T"][0]
    assert transaction[0] == "10"
    assert transaction[4:8] == ["1", "1", "1", "1"]
    assert transaction[12] == "statement-10"
    assert snapshot["H"]


def test_reciprocal_transfer_is_editable() -> None:
    lines = FIXTURE.read_bytes().splitlines(keepends=True)
    for index, line in enumerate(lines):
        if b'Nb="11"' in line:
            lines[index] = (
                line.replace(b'Am="1000.00"', b'Am="-1000.00"')
                .replace(b'Ca="2" Sca="1"', b'Ca="0" Sca="0"')
                .replace(b'Trt="0"', b'Trt="12"')
            )
        elif b'Nb="12"' in line:
            lines[index] = (
                line.replace(b'Ca="2" Sca="1"', b'Ca="0" Sca="0"')
                .replace(b'Trt="0"', b'Trt="11"')
            )
    snapshot = build_account_snapshot(parse_document(b"".join(lines)), "1")
    transfer = next(item for item in snapshot["T"] if item[0] == "11")
    assert transfer[16] & TX_TRANSFER
    assert transfer[17] == "2"


def test_phase5_protocol_returns_compact_json_snapshot() -> None:
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
    assert len(decoded["T"]) == 2
