from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from .errors import ValidationError
from .model import GsbDocument
from .serializer_121 import ATTRIBUTE_ORDER


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    tag: Optional[str] = None
    record_id: Optional[str] = None


def _issue(
    issues: List[ValidationIssue],
    code: str,
    message: str,
    tag: Optional[str] = None,
    record_id: Optional[str] = None,
) -> None:
    issues.append(ValidationIssue(code, message, tag, record_id))


def _is_positive_integer(value: Optional[str]) -> bool:
    if value is None:
        return False
    try:
        return int(value) > 0 and str(int(value)) == value
    except (TypeError, ValueError):
        return False


def _collect_unique(
    root: ET.Element,
    tag: str,
    key_names: Tuple[str, ...],
    issues: List[ValidationIssue],
) -> Dict[Tuple[str, ...], ET.Element]:
    records: Dict[Tuple[str, ...], ET.Element] = {}
    for element in root.findall(tag):
        values = tuple(element.get(name) or "" for name in key_names)
        display_id = "/".join(values)
        if any(not value for value in values):
            _issue(
                issues,
                "missing-key",
                "%s is missing key attribute(s): %s" % (tag, ", ".join(key_names)),
                tag,
                display_id or None,
            )
            continue
        if values in records:
            _issue(
                issues,
                "duplicate-id",
                "Duplicate %s identifier %s" % (tag, display_id),
                tag,
                display_id,
            )
        else:
            records[values] = element
    return records


def _validate_required_attributes(root: ET.Element, issues: List[ValidationIssue]) -> None:
    for tag, names in ATTRIBUTE_ORDER.items():
        for element in root.findall(tag):
            record_id = element.get("Nb")
            missing = [name for name in names if name not in element.attrib]
            if missing:
                _issue(
                    issues,
                    "missing-attributes",
                    "%s %s is missing attributes: %s"
                    % (tag, record_id or "?", ", ".join(missing)),
                    tag,
                    record_id,
                )


def validate_root(
    root: ET.Element,
    expected_file_version: str = "1.2.1",
) -> Tuple[ValidationIssue, ...]:
    issues: List[ValidationIssue] = []
    if root.tag != "Grisbi":
        _issue(issues, "invalid-root", "The XML root element must be Grisbi")
        return tuple(issues)

    generals = root.findall("General")
    if len(generals) != 1:
        _issue(
            issues,
            "general-count",
            "Exactly one General record is required; found %d" % len(generals),
            "General",
        )
    elif generals[0].get("File_version") != expected_file_version:
        _issue(
            issues,
            "file-version",
            "Expected GSB file version %s" % expected_file_version,
            "General",
        )

    _validate_required_attributes(root, issues)

    accounts = _collect_unique(root, "Account", ("Number",), issues)
    currencies = _collect_unique(root, "Currency", ("Nb",), issues)
    payments = _collect_unique(root, "Payment", ("Account", "Number"), issues)
    transactions = _collect_unique(root, "Transaction", ("Nb",), issues)
    parties = _collect_unique(root, "Party", ("Nb",), issues)
    categories = _collect_unique(root, "Category", ("Nb",), issues)
    subcategories = _collect_unique(root, "Sub_category", ("Nbc", "Nb"), issues)

    for (number,), element in accounts.items():
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Account identifier must be a positive integer",
                "Account",
                number,
            )
        currency = element.get("Currency") or ""
        if (currency,) not in currencies:
            _issue(
                issues,
                "missing-currency",
                "Account %s references missing currency %s" % (number, currency),
                "Account",
                number,
            )

    for (number,), element in currencies.items():
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Currency identifier must be a positive integer",
                "Currency",
                number,
            )
        precision = element.get("Fl", "2")
        try:
            if int(precision) < 0 or int(precision) > 12:
                raise ValueError
        except ValueError:
            _issue(
                issues,
                "invalid-currency-precision",
                "Currency %s has invalid precision %s" % (number, precision),
                "Currency",
                number,
            )

    for (account, number), _element in payments.items():
        if (account,) not in accounts:
            _issue(
                issues,
                "missing-account",
                "Payment %s references missing account %s" % (number, account),
                "Payment",
                number,
            )
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Payment identifier must be a positive integer",
                "Payment",
                number,
            )

    for (number,), _element in parties.items():
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Party identifier must be a positive integer",
                "Party",
                number,
            )

    for (number,), element in categories.items():
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Category identifier must be a positive integer",
                "Category",
                number,
            )
        if element.get("Kd") not in ("0", "1", "2"):
            _issue(
                issues,
                "invalid-category-kind",
                "Category %s has invalid Kd" % number,
                "Category",
                number,
            )

    for (category, number), _element in subcategories.items():
        if (category,) not in categories:
            _issue(
                issues,
                "missing-category",
                "Subcategory %s/%s references a missing category"
                % (category, number),
                "Sub_category",
                number,
            )
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Subcategory identifier must be a positive integer",
                "Sub_category",
                number,
            )

    transaction_by_id = {key[0]: element for key, element in transactions.items()}
    for (number,), element in transactions.items():
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Transaction identifier must be a positive integer",
                "Transaction",
                number,
            )

        account = element.get("Ac") or ""
        currency = element.get("Cu") or ""
        party = element.get("Pa") or "0"
        category = element.get("Ca") or "0"
        subcategory = element.get("Sca") or "0"
        payment = element.get("Pn") or "0"

        if (account,) not in accounts:
            _issue(
                issues,
                "missing-account",
                "Transaction %s references missing account %s" % (number, account),
                "Transaction",
                number,
            )
        if (currency,) not in currencies:
            _issue(
                issues,
                "missing-currency",
                "Transaction %s references missing currency %s" % (number, currency),
                "Transaction",
                number,
            )
        if party not in ("0", "(null)") and (party,) not in parties:
            _issue(
                issues,
                "missing-party",
                "Transaction %s references missing party %s" % (number, party),
                "Transaction",
                number,
            )
        if category in ("0", "(null)"):
            if subcategory not in ("0", "(null)"):
                _issue(
                    issues,
                    "subcategory-without-category",
                    "Transaction %s has a subcategory without a category" % number,
                    "Transaction",
                    number,
                )
        else:
            if (category,) not in categories:
                _issue(
                    issues,
                    "missing-category",
                    "Transaction %s references missing category %s"
                    % (number, category),
                    "Transaction",
                    number,
                )
            elif subcategory not in ("0", "(null)") and (
                category,
                subcategory,
            ) not in subcategories:
                _issue(
                    issues,
                    "missing-subcategory",
                    "Transaction %s references missing subcategory %s/%s"
                    % (number, category, subcategory),
                    "Transaction",
                    number,
                )
        if payment not in ("0", "(null)") and (
            account,
            payment,
        ) not in payments:
            _issue(
                issues,
                "missing-payment",
                "Transaction %s references payment %s outside account %s"
                % (number, payment, account),
                "Transaction",
                number,
            )

        try:
            amount = Decimal(element.get("Am", ""))
            if not amount.is_finite():
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            _issue(
                issues,
                "invalid-amount",
                "Transaction %s has an invalid amount" % number,
                "Transaction",
                number,
            )

        transfer = element.get("Trt", "0")
        if transfer not in ("0", "(null)"):
            target = transaction_by_id.get(transfer)
            if target is None:
                _issue(
                    issues,
                    "missing-transfer-target",
                    "Transaction %s references missing transfer %s"
                    % (number, transfer),
                    "Transaction",
                    number,
                )
            elif target.get("Trt", "0") != number:
                _issue(
                    issues,
                    "nonreciprocal-transfer",
                    "Transaction %s transfer link is not reciprocal" % number,
                    "Transaction",
                    number,
                )

        mother = element.get("Mo", "0")
        if mother not in ("0", "(null)") and mother not in transaction_by_id:
            _issue(
                issues,
                "missing-split-mother",
                "Transaction %s references missing split mother %s"
                % (number, mother),
                "Transaction",
                number,
            )

    return tuple(issues)


def validate_document(document: GsbDocument) -> Tuple[ValidationIssue, ...]:
    return validate_root(document.root, expected_file_version=document.file_version)


def assert_valid_document(document: GsbDocument) -> None:
    issues = validate_document(document)
    if issues:
        raise ValidationError(issues)
