from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

pytest.importorskip("Cryptodome")

from ncgrisbi import EnvelopeState, LosslessPatchWriter, inspect_envelope, parse_document
from ncgrisbi.envelope import encode_envelope

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"


def test_real_grisbi_v2_codec_round_trip() -> None:
    plain = FIXTURE.read_bytes()
    for state in (EnvelopeState(False, True, 2), EnvelopeState(True, True, 2)):
        raw = encode_envelope(plain, state, password="phase1-test")
        assert inspect_envelope(raw) == state

        document = parse_document(raw, password="phase1-test")
        assert document.xml_bytes == plain
        assert LosslessPatchWriter(document).render(password="phase1-test") == raw
