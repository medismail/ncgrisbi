class GsbError(Exception):
    """Base exception for the NCGrisbi compatibility engine."""


class EnvelopeError(GsbError):
    """Raised when a GSB compression/encryption envelope is invalid."""


class PasswordRequiredError(EnvelopeError):
    """Raised when encrypted content is opened or written without a password."""


class UnsupportedFileVersionError(GsbError):
    """Raised when a GSB file version is outside the supported profile."""


class PatchConflictError(GsbError):
    """Raised when two byte patches overlap or target invalid ranges."""


class ValidationError(GsbError):
    """Raised when a GSB document violates semantic compatibility rules."""

    def __init__(self, issues):
        self.issues = tuple(issues)
        message = "; ".join(issue.message for issue in self.issues)
        super().__init__(message or "GSB validation failed")


class MutationError(GsbError):
    """Raised when a requested domain mutation is invalid."""


class RecordNotFoundError(MutationError):
    """Raised when a mutation targets a record that does not exist."""


class MutationConflictError(MutationError):
    """Raised when a batch mutates the same record incompatibly."""


class ConfirmationRequiredError(MutationError):
    """Raised when a destructive mutation needs explicit user confirmation."""

    def __init__(self, reason, transaction_ids, message):
        self.reason = str(reason)
        self.transaction_ids = tuple(str(value) for value in transaction_ids)
        super().__init__(message)


class MarkStateError(MutationError):
    """Raised when quick marking targets a telepointed or reconciled row."""
