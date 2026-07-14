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
    try:
        return int(value) > 0 and str(int(value)) == value
    except (TypeError, ValueError):
        return False


def _collect_unique(
    root: ET.Element,
    tag: str,
    key_name: str,
    issues: List[ValidationIssue],
) -> Dict[str, ET.Element]:
    records: Dict[str, ET.Element] = {}
    for element in root.findall(tag):
        value = element.get(key_name) or ""
        if not value:
            _issue(
                issues,
                "missing-key",
                "%s is missing key attribute %s" % (tag, key_name),
                tag,
            )
            continue
        if value in records:
            _issue(
                issues,
                "duplicate-id",
                "Duplicate %s identifier %s" % (tag, value),
                tag,
                value,
            )
        else:
            records[value] = element
    return records


def _collect_subcategories(
    root: ET.Element,
    issues: List[ValidationIssue],
) -> Dict[Tuple[str, str], ET.Element]:
    records: Dict[Tuple[str, str], ET.Element] = {}
    for element in root.findall("Sub_category"):
        key = (element.get("Nbc") or "", element.get("Nb") or "")
        if not all(key):
            _issue(
                issues,
                "missing-key",
                "Sub_category is missing Nbc or Nb",
                "Sub_category",
                "/".join(key),
            )
            continue
        if key in records:
            _issue(
                issues,
                "duplicate-id",
                "Duplicate Sub_category identifier %s/%s" % key,
                "Sub_category",
                key[1],
            )
        else:
            records[key] = element
    return records


def validate_root(
    root: ET.Element,
    expected_file_version: str = "1.2.1",
) -> Tuple[ValidationIssue, ...]:
    issues: List[ValidationIssue] = []
    if root.tag != "Grisbi":
        return (ValidationIssue("invalid-root", "The XML root element must be Grisbi"),)

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

    for tag, names in ATTRIBUTE_ORDER.items():
        for element in root.findall(tag):
            missing = [name for name in names if name not in element.attrib]
            if missing:
                _issue(
                    issues,
                    "missing-attributes",
                    "%s %s is missing attributes: %s"
                    % (tag, element.get("Nb") or "?", ", ".join(missing)),
                    tag,
                    element.get("Nb"),
                )

    accounts = _collect_unique(root, "Account", "Number", issues)
    currencies = _collect_unique(root, "Currency", "Nb", issues)
    # Grisbi identifies a payment method globally by Number. Account is a
    # property used by the form to filter choices; it is not part of the key.
    payments = _collect_unique(root, "Payment", "Number", issues)
    transactions = _collect_unique(root, "Transaction", "Nb", issues)
    parties = _collect_unique(root, "Party", "Nb", issues)
    categories = _collect_unique(root, "Category", "Nb", issues)
    subcategories = _collect_subcategories(root, issues)

    for number, element in accounts.items():
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Account identifier must be a positive integer",
                "Account",
                number,
            )
        currency = element.get("Currency") or ""
        if currency not in currencies:
            _issue(
                issues,
                "missing-currency",
                "Account %s references missing currency %s" % (number, currency),
                "Account",
                number,
            )

    for number, element in currencies.items():
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

    for number, element in payments.items():
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Payment identifier must be a positive integer",
                "Payment",
                number,
            )
        account = element.get("Account") or ""
        if account not in accounts:
            _issue(
                issues,
                "missing-account",
                "Payment %s references missing account %s" % (number, account),
                "Payment",
                number,
            )
        if element.get("Sign", "0") not in ("0", "1", "2"):
            _issue(
                issues,
                "invalid-payment-sign",
                "Payment %s has invalid Sign" % number,
                "Payment",
                number,
            )

    for number in parties:
        if not _is_positive_integer(number):
            _issue(
                issues,
                "invalid-id",
                "Party identifier must be a positive integer",
                "Party",
                number,
            )

    for number, element in categories.items():
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
        if category not in categories:
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

    for number, element in transactions.items():
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

        if account not in accounts:
            _issue(
                issues,
                "missing-account",
                "Transaction %s references missing account %s" % (number, account),
                "Transaction",
                number,
            )
        if currency not in currencies:
            _issue(
                issues,
                "missing-currency",
                "Transaction %s references missing currency %s" % (number, currency),
                "Transaction",
                number,
            )
        if party not in ("0", "(null)") and party not in parties:
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
            if category not in categories:
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

        # Compatibility rule: opening an existing Grisbi file requires only that
        # Pn exists globally. Account/sign suitability is enforced when a user
        # creates or explicitly changes the transaction/payment selection.
        if payment not in ("0", "(null)") and payment not in payments:
            _issue(
                issues,
                "missing-payment",
                "Transaction %s references missing payment %s" % (number, payment),
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
            target = transactions.get(transfer)
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
        if mother not in ("0", "(null)") and mother not in transactions:
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
