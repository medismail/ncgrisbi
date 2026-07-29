from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib" / "bin"))

from ncgrisbi import (
    LosslessPatchWriter,
    PatchConflictError,
    UnsupportedFileVersionError,
    parse_document,
    serialize_record,
)

FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"


def test_scanner_maps_every_top_level_record_exactly() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)

    assert len(document.spans) == len(list(document.root)) == 16
    assert [span.tag for span in document.spans] == [node.tag for node in document.root]
    assert document.find_span("Transaction", "Nb", "10").raw(original).startswith(
        b'<Transaction Ac="1" Nb="10"'
    )


def test_scanner_is_quote_aware_and_supports_multiline_records() -> None:
    raw = (
        b'<?xml version="1.0"?>\n<Grisbi>\n'
        b'\t<General File_version="1.2.1" Grisbi_version="1.2.2" />\n'
        b'\t<Party Nb="1"\n\t\tNa="A > B" Txt="(null)" Search="(null)" '
        b'IgnCase="0" UseRegex="0" />\n'
        b'</Grisbi>\n'
    )
    document = parse_document(raw)
    party = document.spans_for("Party")[0]

    assert party.raw(raw).endswith(b'UseRegex="0" />')
    assert b'A > B' in party.raw(raw)


def test_replace_record_changes_only_the_target_record() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)
    span = document.find_span("Transaction", "Nb", "10")
    assert span is not None
    element = document.element_for_span(span)
    assert element is not None
    attributes = dict(element.attrib)
    attributes["No"] = 'Updated "note" & detail'

    writer = LosslessPatchWriter(document)
    writer.replace_record(span, attributes)
    output = writer.render_xml()

    old_record = span.raw(original)
    new_record = serialize_record("Transaction", attributes)
    assert output == original[:span.start] + new_record + original[span.end:]
    assert old_record not in output
    assert b'No="Updated &quot;note&quot; &amp; detail"' in output


def test_insert_party_uses_the_correct_section_anchor() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)
    writer = LosslessPatchWriter(document)
    attributes = {
        "Nb": "3",
        "Na": "New payee",
        "Txt": None,
        "Search": None,
        "IgnCase": "0",
        "UseRegex": "0",
    }

    writer.insert_record("Party", attributes)
    output = writer.render_xml()
    inserted = b'\t' + serialize_record("Party", attributes) + b'\n'

    assert output.replace(inserted, b"", 1) == original
    assert output.index(inserted) < output.index(b'\t<Category Nb="1"')
    assert ET.fromstring(output).findall("Party")[-1].get("Nb") == "3"


def test_explicit_anchor_supports_interleaved_category_sections() -> None:
    original = FIXTURE.read_bytes()
    document = parse_document(original)
    category = document.find_span("Category", "Nb", "1")
    assert category is not None
    attributes = {"Nbc": "1", "Nb": "2", "Na": "Water"}

    writer = LosslessPatchWriter(document)
    writer.insert_record("Sub_category", attributes, after=category)
    output = writer.render_xml()
    inserted = b'\t' + serialize_record("Sub_category", attributes) + b'\n'

    assert output.index(inserted) == category.line_end


def test_overlapping_replacements_are_rejected() -> None:
    document = parse_document(FIXTURE.read_bytes())
    span = document.find_span("Party", "Nb", "1")
    assert span is not None
    element = document.element_for_span(span)
    assert element is not None

    writer = LosslessPatchWriter(document)
    writer.replace_record(span, dict(element.attrib))
    writer.replace_record(span, dict(element.attrib))
    with pytest.raises(PatchConflictError):
        writer.render_xml()


def test_unsupported_file_version_is_rejected() -> None:
    raw = FIXTURE.read_bytes().replace(b'File_version="1.2.1"', b'File_version="2.0.0"')
    with pytest.raises(UnsupportedFileVersionError):
        parse_document(raw)
