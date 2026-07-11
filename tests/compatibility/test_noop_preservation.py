from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "compatibility" / "fixtures" / "grisbi-1.2.2-basic.gsb"


def load_current_grisbi_module():
    module_path = ROOT / "lib" / "bin" / "grisbi.py"
    module_name = "ncgrisbi_phase0_noop"
    sys.modules.setdefault("gsb_decode", types.ModuleType("gsb_decode"))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Phase 1 must replace whole-document ElementTree serialization with a "
        "lossless patch writer. This expected failure is the compatibility gate."
    ),
)
def test_noop_save_is_byte_identical() -> None:
    grisbi = load_current_grisbi_module()
    original = FIXTURE.read_bytes()
    root = grisbi.parse_gsb_content(original)
    assert root is not None

    rewritten = grisbi.write_gsb_content(root).encode("utf-8")
    assert rewritten == original
