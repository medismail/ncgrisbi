"""Deprecated import shim for the consolidated framed worker.

Application entrypoints must import :mod:`ncgrisbi.worker`. This module remains
for one compatibility cycle so existing tests and third-party imports can move
to the responsibility-named worker without changing production behavior.
"""

from .worker import _account_id, _raw_operations, error_response, execute_request, main

__all__ = [
    "_account_id",
    "_raw_operations",
    "error_response",
    "execute_request",
    "main",
]
