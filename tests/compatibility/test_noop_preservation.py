from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi import LosslessPatchWriter, parse_document

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"


def test_noop_save_is_byte_identical() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)
    writer = LosslessPatchWriter(document)

    assert writer.render_xml() == original
    assert writer.render() == original
