from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping

from .formats import GSB_121_PROFILE

# Compatibility exports retained for callers and tests while schema ownership
# moves to the versioned format profile.
ATTRIBUTE_ORDER = GSB_121_PROFILE.attribute_order


def serialize_record(tag: str, attributes: Mapping) -> bytes:
    return GSB_121_PROFILE.serialize_record(tag, attributes)


def serialize_element(element: ET.Element) -> bytes:
    return serialize_record(element.tag, element.attrib)
