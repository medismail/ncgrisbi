"""Canonical mutation API.

The implementation is consolidated behind this responsibility-named module.
The private compatibility core is removed after imports and tests migrate.
"""

from .mutation_engine import (
    MutationResult,
    MutationSession,
    apply_mutations,
)

__all__ = ["MutationResult", "MutationSession", "apply_mutations"]
