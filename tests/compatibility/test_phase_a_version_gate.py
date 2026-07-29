from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib" / "bin"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from ncgrisbi.errors import UnsupportedFileVersionError
from ncgrisbi.formats import supported_file_versions
from ncgrisbi.parser import parse_document


def minimal_file(file_version: str, grisbi_version: str) -> bytes:
    return (
        '<?xml version="1.0"?>\n'
        '<Grisbi>\n'
        '<General File_version="%s" Grisbi_version="%s" />\n'
        '</Grisbi>'
        % (file_version, grisbi_version)
    ).encode("utf-8")


def test_phase_a_keeps_the_121_write_target() -> None:
    assert supported_file_versions() == ("1.2.1",)
    document = parse_document(
        minimal_file("1.2.1", "1.2.2"),
        accepted_file_versions=(),
    )
    assert document.file_version == "1.2.1"
    assert document.format_profile is not None
    assert document.format_profile.file_version == "1.2.1"


def test_phase_a_does_not_enable_232_implicitly() -> None:
    with pytest.raises(UnsupportedFileVersionError):
        parse_document(minimal_file("2.3.2", "3.90.1"))
