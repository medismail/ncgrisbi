from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Dict, Mapping, Tuple
from xml.sax.saxutils import escape


class SupportLevel(str, Enum):
    """Capabilities granted to a detected Grisbi file format."""

    READ_ONLY = "read-only"
    READ_WRITE = "read-write"


@dataclass(frozen=True)
class FormatProfile:
    """All schema and write rules owned by one GSB file version."""

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
