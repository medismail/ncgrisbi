from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "lib" / "bin" / "ncgrisbi"


def test_target_backend_has_the_exact_top_level_file_set() -> None:
    expected = {
        "__init__.py",
        "_mutation_core.py",
        "_snapshot_core.py",
        "envelope.py",
        "errors.py",
        "framing.py",
        "model.py",
        "mutation.py",
        "parser.py",
        "read.py",
        "snapshot.py",
        "validator.py",
        "worker.py",
        "writer.py",
    }
    actual = {
        path.name
        for path in PACKAGE.iterdir()
        if path.is_file() and path.suffix == ".py"
    }
    assert actual == expected


def test_format_profiles_have_an_exact_isolated_layout() -> None:
    formats = PACKAGE / "formats"
    expected = {"__init__.py", "base.py", "gsb_121.py"}
    actual = {
        path.name
        for path in formats.iterdir()
        if path.is_file() and path.suffix == ".py"
    }
    assert actual == expected


def test_no_version_232_profile_exists() -> None:
    assert not any("232" in path.name for path in (PACKAGE / "formats").iterdir())
