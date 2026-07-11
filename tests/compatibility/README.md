# GSB compatibility tests

This directory contains the executable compatibility contract for Grisbi 1.2.2 files whose `File_version` is `1.2.1`.

- `fixtures/` contains representative account documents and provenance metadata.
- `expected/` contains exact canonical records copied into the fixture.
- `test_gsb_121_contract.py` checks format, ordering, references and the existing reader.
- `test_noop_preservation.py` is the Phase 1 gate for lossless writing.

The fixture data is synthetic and contains no real financial information.
