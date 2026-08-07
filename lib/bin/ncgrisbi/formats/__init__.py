from __future__ import annotations

from types import MappingProxyType
from typing import Optional, Sequence, Tuple

from ..errors import UnsupportedFileVersionError
from .base import FormatProfile, SupportLevel
from .gsb_121 import ATTRIBUTE_ORDER as GSB_121_ATTRIBUTE_ORDER
from .gsb_121 import PROFILE as GSB_121_PROFILE
from .gsb_200 import ATTRIBUTE_ORDER as GSB_200_ATTRIBUTE_ORDER
from .gsb_200 import PROFILE as GSB_200_PROFILE

_PROFILES = MappingProxyType({GSB_121_PROFILE.file_version: GSB_121_PROFILE, GSB_200_PROFILE.file_version: GSB_200_PROFILE})


def supported_file_versions() -> Tuple[str, ...]:
    return tuple(_PROFILES)


def get_format_profile(file_version: str) -> Optional[FormatProfile]:
    return _PROFILES.get(file_version)


def require_format_profile(
    file_version: str,
    accepted_file_versions: Optional[Sequence[str]] = None,
) -> FormatProfile:
    # Preserve the historical parser contract: an empty accepted-version
    # sequence means "use the backend registry", not "accept no versions".
    if accepted_file_versions and file_version not in accepted_file_versions:
        raise UnsupportedFileVersionError(
            "Unsupported GSB file version: %s" % (file_version or "missing")
        )
    profile = get_format_profile(file_version)
    if profile is None:
        raise UnsupportedFileVersionError(
            "Unsupported GSB file version: %s" % (file_version or "missing")
        )
    return profile


__all__ = [
    "FormatProfile",
    "GSB_121_ATTRIBUTE_ORDER",
    "GSB_121_PROFILE",
    "GSB_200_ATTRIBUTE_ORDER",
    "GSB_200_PROFILE",
    "SupportLevel",
    "get_format_profile",
    "require_format_profile",
    "supported_file_versions",
]
