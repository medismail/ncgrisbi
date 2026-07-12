#!/usr/bin/env python3
"""Secure descriptor wrapper for the pre-Phase-3 read-only CLI.

The legacy script still expects ``--pass-word`` in ``sys.argv``. This wrapper
reads the secret from descriptor 3 and adds it only to the in-process Python
argument list, never to the operating-system process command line or environment.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

MAX_PASSWORD_BYTES = 64 * 1024


def read_password(fd: int = 3):
    chunks = []
    total = 0
    while True:
        chunk = os.read(fd, 4096)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_PASSWORD_BYTES:
            raise RuntimeError("Password exceeds the transport limit")
        chunks.append(chunk)
    if not chunks:
        return None
    return b"".join(chunks).decode("utf-8")


def main() -> int:
    password = read_password(3)
    legacy = Path(__file__).with_name("grisbi.py")
    arguments = [str(legacy)] + sys.argv[1:]
    if password is not None:
        arguments.extend(["--pass-word", password])
    sys.argv = arguments
    runpy.run_path(str(legacy), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
