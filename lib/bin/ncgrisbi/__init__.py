"""Lossless, version-profiled Grisbi compatibility backend."""

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
    GSB_121_PROFILE,
    SupportLevel,
    get_format_profile,
    require_format_profile,
    supported_file_versions,
)
from .index import GsbIndex, IndexedRecord
from .model import ElementSpan, GsbDocument
from .mutation_engine import (
    MutationResult,
    Phase6Result,
    apply_mutations,
    apply_phase6_operations,
)
# Legacy typed-operation exports remain for one compatibility cycle. They are
# not used by the application worker; all live mutations go through
# mutation_engine.apply_mutations.
from .mutations import (
    CreateCategory,
    CreateParty,
    CreateSubcategory,
    CreateTransaction,
    DeleteTransaction,
    MutationEngine,
    MutationOutcome,
    UpdateTransaction,
)
from .parser import parse_document, scan_top_level_spans
from .serializer_121 import ATTRIBUTE_ORDER, serialize_element, serialize_record
from .snapshot_service import build_account_snapshot
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
    "FormatProfile",
    "GSB_121_PROFILE",
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
    "SupportLevel",
    "UnsupportedFileVersionError",
    "UpdateTransaction",
    "ValidationError",
    "ValidationIssue",
    "apply_mutations",
    "apply_phase6_operations",
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
    "serialize_element",
    "serialize_record",
    "supported_file_versions",
    "validate_document",
    "validate_root",
    "warning_issues",
]
