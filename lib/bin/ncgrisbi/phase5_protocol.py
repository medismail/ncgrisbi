"""Deprecated import shim for the consolidated framed worker.

Application entrypoints must import :mod:`ncgrisbi.worker`. This module remains
for one compatibility cycle so existing tests and third-party imports fail
cleanly only after the migration contract is complete.
"""

from .worker import error_response, execute_request, main

__all__ = ["error_response", "execute_request", "main"]
