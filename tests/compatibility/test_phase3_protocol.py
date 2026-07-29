from __future__ import annotations

import io
import json
import os
import struct
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lib' / 'bin'))

from ncgrisbi.mutations import CreateParty, UpdateTransaction
import ncgrisbi.protocol as protocol_module
from ncgrisbi.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    decode_operation,
    encode_frame,
    error_response,
    execute_request,
    read_frame,
    read_password_fd,
)


def test_binary_frame_round_trip() -> None:
    payload = b'\x00GSB\xffpayload'
    encoded = encode_frame({'version': 1, 'command': 'mutate'}, payload)
    header, decoded = read_frame(io.BytesIO(encoded))
    assert header['payloadLength'] == len(payload)
    assert decoded == payload


def test_frame_rejects_truncated_and_mismatched_payloads() -> None:
    with pytest.raises(ProtocolError):
        read_frame(io.BytesIO(b'\x00\x00'))

    header = json.dumps({'payloadLength': 4}).encode()
    raw = struct.pack('!I', len(header)) + header + b'abc'
    with pytest.raises(ProtocolError):
        read_frame(io.BytesIO(raw))


def test_camel_case_operations_are_translated() -> None:
    party = decode_operation({'type': 'createParty', 'name': 'A', 'ignoreCase': True})
    assert isinstance(party, CreateParty)
    assert party.ignore_case is True

    update = decode_operation({
        'type': 'updateTransaction',
        'transactionId': '10',
        'changes': {'accountId': '2', 'bankReference': 'ref'},
    })
    assert isinstance(update, UpdateTransaction)
    assert update.changes == {'account_id': '2', 'bank_reference': 'ref'}


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ProtocolError):
        decode_operation({'type': 'createParty', 'name': 'A', 'typo': 1})


def test_execute_request_returns_binary_output_and_outcomes(monkeypatch) -> None:
    def fake_apply(payload, operations, password=None):
        assert password == 'secret'
        assert len(operations) == 1
        return SimpleNamespace(
            raw_bytes=payload + b'!',
            outcomes=(SimpleNamespace(
                operation_index=0,
                operation='CreateParty',
                record_type='Party',
                record_id='1',
            ),),
        )

    monkeypatch.setattr(protocol_module, 'apply_mutations', fake_apply)
    header = {
        'version': PROTOCOL_VERSION,
        'command': 'mutate',
        'requestId': 'req-1',
        'operations': [{'type': 'createParty', 'name': 'A'}],
    }
    response, output = execute_request(header, b'gsb', 'secret')
    assert response['ok'] is True
    assert response['requestId'] == 'req-1'
    assert response['changed'] is True
    assert response['outcomes'][0]['recordId'] == '1'
    assert output == b'gsb!'


def test_password_is_read_only_from_dedicated_descriptor() -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, 'päss word'.encode('utf-8'))
    os.close(write_fd)
    try:
        assert read_password_fd(read_fd) == 'päss word'
    finally:
        os.close(read_fd)


def test_domain_errors_have_stable_codes() -> None:
    response = error_response(ProtocolError('bad request'), request_id='x')
    assert response['ok'] is False
    assert response['requestId'] == 'x'
    assert response['error']['code'] == 'invalid-protocol'
