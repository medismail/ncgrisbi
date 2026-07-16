"""Lossless Grisbi 1.2.2 / GSB 1.2.1 compatibility and mutation engine."""

from .envelope import (
    DecodedEnvelope,
    EnvelopeState,
    decode_envelope,
    encode_envelope,
    inspect_envelope,
)
from .errors import (
    ConfirmationRequiredError,
    EnvelopeError,
    GsbError,
    MarkStateError,
    MutationConflictError,
    MutationError,
    PasswordRequiredError,
    PatchConflictError,
    RecordNotFoundError,
    UnsupportedFileVersionError,
    ValidationError,
)
from .index import GsbIndex, IndexedRecord
from .model import ElementSpan, GsbDocument
from .mutations import (
    CreateCategory,
    CreateParty,
    CreateSubcategory,
    CreateTransaction,
    DeleteTransaction,
    MutationEngine,
    MutationOutcome,
    MutationResult,
    UpdateTransaction,
    apply_mutations,
)
from .parser import parse_document, scan_top_level_spans
from .phase6_engine import Phase6Result, apply_phase6_operations
from .serializer_121 import ATTRIBUTE_ORDER, serialize_element, serialize_record
from .validator import (
    ValidationIssue,
    assert_valid_document,
    fatal_issues,
    validate_document,
    validate_root,
    warning_issues,
)
from .writer import LosslessPatchWriter, Patch

__all__ = [
    "ATTRIBUTE_ORDER",
    "ConfirmationRequiredError",
    "CreateCategory",
    "CreateParty",
    "CreateSubcategory",
    "CreateTransaction",
    "DecodedEnvelope",
    "DeleteTransaction",
    "ElementSpan",
    "EnvelopeError",
    "EnvelopeState",
    "GsbDocument",
    "GsbError",
    "GsbIndex",
    "IndexedRecord",
    "LosslessPatchWriter",
    "MarkStateError",
    "MutationConflictError",
    "MutationEngine",
    "MutationError",
    "MutationOutcome",
    "MutationResult",
    "PasswordRequiredError",
    "Patch",
    "PatchConflictError",
    "Phase6Result",
    "RecordNotFoundError",
    "UnsupportedFileVersionError",
    "UpdateTransaction",
    "ValidationError",
    "ValidationIssue",
    "apply_mutations",
    "apply_phase6_operations",
    "assert_valid_document",
    "decode_envelope",
    "encode_envelope",
    "fatal_issues",
    "inspect_envelope",
    "parse_document",
    "scan_top_level_spans",
    "serialize_element",
    "serialize_record",
    "validate_document",
    "validate_root",
    "warning_issues",
]
