from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import List
from xml.sax.saxutils import escape

ATTRIBUTE_ORDER = {
    "Transaction": (
        "Ac", "Nb", "Id", "Dt", "Dv", "Cu", "Am", "Exb", "Exr", "Exf",
        "Pa", "Ca", "Sca", "Br", "No", "Pn", "Pc", "Ma", "Ar", "Au",
        "Re", "Fi", "Bu", "Sbu", "Vo", "Ba", "Trt", "Mo",
    ),
    "Party": ("Nb", "Na", "Txt", "Search", "IgnCase", "UseRegex"),
    "Category": ("Nb", "Na", "Kd"),
    "Sub_category": ("Nbc", "Nb", "Na"),
}


def _attribute_value(value) -> str:
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


def serialize_record(tag: str, attributes: Mapping) -> bytes:
    if tag not in ATTRIBUTE_ORDER:
        raise ValueError("No Grisbi 1.2.1 serializer is defined for %s" % tag)

    canonical = ATTRIBUTE_ORDER[tag]
    missing = [name for name in canonical if name not in attributes]
    if missing:
        raise ValueError(
            "%s is missing required attributes: %s" % (tag, ", ".join(missing))
        )

    names: List[str] = list(canonical)
    names.extend(name for name in attributes if name not in canonical)
    parts = [
        '%s="%s"' % (name, _attribute_value(attributes[name]))
        for name in names
    ]
    return ("<%s %s />" % (tag, " ".join(parts))).encode("utf-8")


def serialize_element(element: ET.Element) -> bytes:
    return serialize_record(element.tag, element.attrib)
