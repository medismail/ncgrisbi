"""Lossless, version-profiled Grisbi backend."""

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
from .formats import (
    FormatProfile,
    GSB_121_ATTRIBUTE_ORDER,
    GSB_121_PROFILE,
    SupportLevel,
    get_format_profile,
    require_format_profile,
    supported_file_versions,
)
from .index import GsbIndex, IndexedRecord
from .model import ElementSpan, GsbDocument
from .mutation import MutationResult, MutationSession, apply_mutations
from .parser import parse_document, scan_top_level_spans
from .snapshot import build_account_snapshot
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
    "ConfirmationRequiredError",
    "DecodedEnvelope",
    "ElementSpan",
    "EnvelopeError",
    "EnvelopeState",
    "FormatProfile",
    "GSB_121_ATTRIBUTE_ORDER",
    "GSB_121_PROFILE",
    "GsbDocument",
    "GsbError",
    "GsbIndex",
    "IndexedRecord",
    "LosslessPatchWriter",
    "MarkStateError",
    "MutationConflictError",
    "MutationError",
    "MutationResult",
    "MutationSession",
    "PasswordRequiredError",
    "Patch",
    "PatchConflictError",
    "RecordNotFoundError",
    "SupportLevel",
    "UnsupportedFileVersionError",
    "ValidationError",
    "ValidationIssue",
    "apply_mutations",
    "assert_valid_document",
    "build_account_snapshot",
    "decode_envelope",
    "encode_envelope",
    "fatal_issues",
    "get_format_profile",
    "inspect_envelope",
    "parse_document",
    "require_format_profile",
    "scan_top_level_spans",
    "supported_file_versions",
    "validate_document",
    "validate_root",
    "warning_issues",
]
