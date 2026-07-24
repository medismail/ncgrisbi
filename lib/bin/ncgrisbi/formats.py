from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Dict, Mapping, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from .errors import UnsupportedFileVersionError


class SupportLevel(str, Enum):
    """Capabilities granted to a detected Grisbi file format."""

    READ_ONLY = "read-only"
    READ_WRITE = "read-write"


@dataclass(frozen=True)
class FormatProfile:
    """Version-specific schema and write policy for one GSB format.

    The lossless XML parser and byte patch writer are deliberately version
    neutral. Everything that can vary between Grisbi file generations belongs
    here: record schemas, section placement, creation defaults and capabilities.
    """

    file_version: str
    application_target: str
    support_level: SupportLevel
    section_groups: Tuple[Tuple[str, ...], ...]
    attribute_order: Mapping[str, Tuple[str, ...]]
    record_defaults: Mapping[str, Mapping[str, str]]
    capabilities: frozenset[str]

    @property
    def section_rank(self) -> Mapping[str, int]:
        return MappingProxyType(
            {
                tag: rank
                for rank, group in enumerate(self.section_groups)
                for tag in group
            }
        )

    def serialize_record(self, tag: str, attributes: Mapping[str, object]) -> bytes:
        canonical = self.attribute_order.get(tag)
        if canonical is None:
            raise ValueError(
                "No Grisbi %s serializer is defined for %s"
                % (self.file_version, tag)
            )

        missing = [name for name in canonical if name not in attributes]
        if missing:
            raise ValueError(
                "%s is missing required attributes: %s"
                % (tag, ", ".join(missing))
            )

        names = list(canonical)
        names.extend(name for name in attributes if name not in canonical)
        parts = [
            '%s="%s"' % (name, _attribute_value(attributes[name]))
            for name in names
        ]
        return ("<%s %s />" % (tag, " ".join(parts))).encode("utf-8")

    def defaults_for(self, tag: str) -> Dict[str, str]:
        try:
            defaults = self.record_defaults[tag]
        except KeyError as exc:
            raise ValueError(
                "No Grisbi %s defaults are defined for %s"
                % (self.file_version, tag)
            ) from exc
        return dict(defaults)

    def new_transaction_attributes(
        self,
        *,
        account_id: str,
        transaction_id: str,
        date: str,
        value_date: str,
        currency_id: str,
        amount: str,
        party_id: str,
        payment_id: str,
    ) -> Dict[str, str]:
        attributes = self.defaults_for("Transaction")
        attributes.update(
            {
                "Ac": account_id,
                "Nb": transaction_id,
                "Dt": date,
                "Dv": value_date,
                "Cu": currency_id,
                "Am": amount,
                "Pa": party_id,
                "Pn": payment_id,
            }
        )
        return attributes


def _attribute_value(value: object) -> str:
    if value is None:
        text = "(null)"
    elif isinstance(value, bool):
        text = "1" if value else "0"
    else:
        text = str(value)
    return escape(
        text,
        {
            '"': "&quot;",
            "\r": "&#13;",
            "\n": "&#10;",
            "\t": "&#9;",
        },
    )


_GSB_121_ATTRIBUTE_ORDER = MappingProxyType(
    {
        "Transaction": (
            "Ac", "Nb", "Id", "Dt", "Dv", "Cu", "Am", "Exb", "Exr", "Exf",
            "Pa", "Ca", "Sca", "Br", "No", "Pn", "Pc", "Ma", "Ar", "Au",
            "Re", "Fi", "Bu", "Sbu", "Vo", "Ba", "Trt", "Mo",
        ),
        "Party": ("Nb", "Na", "Txt", "Search", "IgnCase", "UseRegex"),
        "Category": ("Nb", "Na", "Kd"),
        "Sub_category": ("Nbc", "Nb", "Na"),
    }
)

_GSB_121_DEFAULTS = MappingProxyType(
    {
        "Transaction": MappingProxyType(
            {
                "Ac": "0",
                "Nb": "0",
                "Id": "(null)",
                "Dt": "(null)",
                "Dv": "(null)",
                "Cu": "0",
                "Am": "0.00",
                "Exb": "0",
                "Exr": "0.00",
                "Exf": "0.00",
                "Pa": "0",
                "Ca": "0",
                "Sca": "0",
                "Br": "0",
                "No": "(null)",
                "Pn": "0",
                "Pc": "(null)",
                "Ma": "0",
                "Ar": "0",
                "Au": "0",
                "Re": "0",
                "Fi": "0",
                "Bu": "0",
                "Sbu": "0",
                "Vo": "(null)",
                "Ba": "(null)",
                "Trt": "0",
                "Mo": "0",
            }
        ),
        "Party": MappingProxyType(
            {
                "Nb": "0",
                "Na": "",
                "Txt": "(null)",
                "Search": "(null)",
                "IgnCase": "0",
                "UseRegex": "0",
            }
        ),
        "Category": MappingProxyType({"Nb": "0", "Na": "", "Kd": "0"}),
        "Sub_category": MappingProxyType({"Nbc": "0", "Nb": "0", "Na": ""}),
    }
)

GSB_121_PROFILE = FormatProfile(
    file_version="1.2.1",
    application_target="Grisbi 1.2.2",
    support_level=SupportLevel.READ_WRITE,
    section_groups=(
        ("General",),
        ("RGBA",),
        ("Print",),
        ("Currency",),
        ("Account",),
        ("Payment",),
        ("Transaction",),
        ("Scheduled",),
        ("Party",),
        ("Category", "Sub_category"),
        ("Budgetary", "Sub_budgetary"),
        ("Currency_link",),
        ("Bank",),
        ("Financial_year",),
        ("Archive",),
        ("Reconcile",),
        ("Import_rule",),
        ("Partial_balance",),
        ("Bet",),
        ("Report",),
    ),
    attribute_order=_GSB_121_ATTRIBUTE_ORDER,
    record_defaults=_GSB_121_DEFAULTS,
    capabilities=frozenset(
        {
            "read-accounts",
            "read-transactions",
            "patch-mark",
            "update-normal-transaction",
            "create-normal-transaction",
            "delete-normal-transaction",
            "edit-transfer",
            "create-party",
            "create-category",
        }
    ),
)

_PROFILES = MappingProxyType({GSB_121_PROFILE.file_version: GSB_121_PROFILE})


def supported_file_versions() -> Tuple[str, ...]:
    return tuple(_PROFILES)


def get_format_profile(file_version: str) -> Optional[FormatProfile]:
    return _PROFILES.get(file_version)


def require_format_profile(
    file_version: str,
    accepted_file_versions: Optional[Sequence[str]] = None,
) -> FormatProfile:
    if accepted_file_versions is not None and file_version not in accepted_file_versions:
        raise UnsupportedFileVersionError(
            "Unsupported GSB file version: %s" % (file_version or "missing")
        )
    profile = get_format_profile(file_version)
    if profile is None:
        raise UnsupportedFileVersionError(
            "Unsupported GSB file version: %s" % (file_version or "missing")
        )
    return profile
