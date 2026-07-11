from pathlib import Path
import gzip
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi import (
    EnvelopeError,
    EnvelopeState,
    LosslessPatchWriter,
    PasswordRequiredError,
    decode_envelope,
    encode_envelope,
    inspect_envelope,
    parse_document,
)

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"
MARKER = b"Grisbi encryption v2: "


class FakeCrypto(types.SimpleNamespace):
    @staticmethod
    def encrypt_v2(password, payload):
        if password != "secret":
            raise ValueError("bad password")
        return MARKER + b"ENC:" + bytes(payload)

    @staticmethod
    def decrypt_v2(password, payload):
        if password != "secret" or not payload.startswith(MARKER + b"ENC:"):
            raise ValueError("bad password")
        return payload[len(MARKER + b"ENC:"):]


@pytest.fixture(autouse=True)
def fake_crypto(monkeypatch):
    monkeypatch.setitem(sys.modules, "gsb_decode", FakeCrypto())


def test_plain_and_gzip_envelopes_are_detected() -> None:
    plain = FIXTURE.read_bytes()
    compressed = gzip.compress(plain, mtime=123)

    assert inspect_envelope(plain) == EnvelopeState(False, False)
    assert inspect_envelope(compressed) == EnvelopeState(True, False)
    assert decode_envelope(compressed).xml_bytes == plain


def test_gzip_wrapped_encrypted_file_uses_reverse_read_order() -> None:
    plain = FIXTURE.read_bytes()
    encrypted = encode_envelope(plain, EnvelopeState(False, True), password="secret")
    wrapped = gzip.compress(encrypted, mtime=123)

    assert inspect_envelope(wrapped) == EnvelopeState(True, True)
    decoded = decode_envelope(wrapped, password="secret")
    assert decoded.xml_bytes == plain
    assert decoded.state == EnvelopeState(True, True)


def test_noop_returns_original_compressed_or_encrypted_bytes() -> None:
    plain = FIXTURE.read_bytes()
    variants = [
        gzip.compress(plain, mtime=123),
        encode_envelope(plain, EnvelopeState(False, True), password="secret"),
        encode_envelope(plain, EnvelopeState(True, True), password="secret"),
    ]

    for raw in variants:
        document = parse_document(raw, password="secret")
        assert LosslessPatchWriter(document).render(password="secret") == raw


def test_mutation_preserves_envelope_type() -> None:
    plain = FIXTURE.read_bytes()
    raw = encode_envelope(plain, EnvelopeState(True, True), password="secret")
    document = parse_document(raw, password="secret")
    writer = LosslessPatchWriter(document)
    writer.insert_record(
        "Party",
        {
            "Nb": "3",
            "Na": "Envelope test",
            "Txt": None,
            "Search": None,
            "IgnCase": "0",
            "UseRegex": "0",
        },
    )

    output = writer.render(password="secret")
    assert inspect_envelope(output) == EnvelopeState(True, True)
    reopened = parse_document(output, password="secret")
    assert reopened.root.findall("Party")[-1].get("Na") == "Envelope test"


def test_encrypted_files_require_a_password() -> None:
    raw = MARKER + b"ENC:data"
    with pytest.raises(PasswordRequiredError):
        decode_envelope(raw)
    with pytest.raises(EnvelopeError):
        decode_envelope(raw, password="wrong")
