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
