"""Canonical NCGrisbi mutation engine.

The implementation remains in ``phase6_engine`` during the compatibility
transition so existing imports and tests keep working. New application code
must import this module; the phase-numbered module is now an implementation
compatibility shim rather than a second mutation path.
"""

from .phase6_engine import Phase6Result, apply_phase6_operations

MutationResult = Phase6Result
apply_mutations = apply_phase6_operations

__all__ = [
    "MutationResult",
    "Phase6Result",
    "apply_mutations",
    "apply_phase6_operations",
]
