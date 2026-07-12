from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .errors import MutationError, RecordNotFoundError

_NULL_VALUES = (None, "(null)")


def _nullable(value: Optional[str]) -> Optional[str]:
    return None if value in _NULL_VALUES else value


def _canonical_positive_id(value: Any, field: str) -> str:
    text = str(value)
    try:
        number = int(text)
    except (TypeError, ValueError):
        raise MutationError("%s must be a numeric Grisbi identifier" % field)
    if number <= 0 or str(number) != text:
        raise MutationError("%s is not a canonical positive Grisbi identifier" % field)
    return text


def _numeric_key(value: str) -> Tuple[int, str]:
    try:
        return int(value), value
    except (TypeError, ValueError):
        return 2 ** 31 - 1, str(value)


def _decimal(value: Optional[str], field: str) -> Decimal:
    try:
        result = Decimal(value or "")
    except (InvalidOperation, ValueError):
        raise MutationError("%s is not a valid decimal number" % field)
    if not result.is_finite():
        raise MutationError("%s must be finite" % field)
    return result


def _format_decimal(value: Decimal, precision: int) -> str:
    quantum = Decimal(1).scaleb(-precision)
    return format(value.quantize(quantum), ".%df" % precision)


def _index_by_attribute(elements: Iterable[Any], attribute: str) -> Dict[str, Any]:
    indexed: Dict[str, Any] = {}
    for element in elements:
        key = element.get(attribute)
        if key is not None:
            indexed[key] = element
    return indexed


def _protection(attributes: Mapping[str, str]) -> List[str]:
    reasons: List[str] = []
    if attributes.get("Br", "0") not in ("0", "(null)"):
        reasons.append("breakdown")
    if attributes.get("Trt", "0") not in ("0", "(null)"):
        reasons.append("transfer")
    if attributes.get("Mo", "0") not in ("0", "(null)"):
        reasons.append("split-child")
    return reasons


def build_account_snapshot(document: Any, account_id: Any) -> Dict[str, Any]:
    """Build the typed Phase 5 editor snapshot from a validated GSB document."""
    account_id = _canonical_positive_id(account_id, "accountId")
    root = document.root

    accounts = _index_by_attribute(root.findall("Account"), "Number")
    account = accounts.get(account_id)
    if account is None:
        raise RecordNotFoundError("Account %s does not exist" % account_id)

    currencies = _index_by_attribute(root.findall("Currency"), "Nb")
    currency_id = account.get("Currency") or ""
    currency = currencies.get(currency_id)
    if currency is None:
        raise MutationError(
            "Account %s references missing currency %s" % (account_id, currency_id)
        )
    try:
        precision = int(currency.get("Fl", "2"))
    except ValueError:
        raise MutationError("Currency %s has invalid precision" % currency_id)
    if precision < 0 or precision > 12:
        raise MutationError("Currency %s has unsupported precision" % currency_id)

    party_elements = list(root.findall("Party"))
    parties_by_id = _index_by_attribute(party_elements, "Nb")
    parties = [
        {"id": element.get("Nb"), "name": element.get("Na") or ""}
        for element in sorted(
            party_elements,
            key=lambda element: _numeric_key(element.get("Nb") or ""),
        )
    ]

    category_elements = list(root.findall("Category"))
    categories_by_id = _index_by_attribute(category_elements, "Nb")
    subcategories_by_key: Dict[Tuple[str, str], Any] = {}
    subcategories_by_category: Dict[str, List[Dict[str, str]]] = {}
    for element in root.findall("Sub_category"):
        category = element.get("Nbc") or ""
        number = element.get("Nb") or ""
        subcategories_by_key[(category, number)] = element
        subcategories_by_category.setdefault(category, []).append(
            {"id": number, "name": element.get("Na") or ""}
        )
    for values in subcategories_by_category.values():
        values.sort(key=lambda item: _numeric_key(item["id"]))

    categories = []
    for element in sorted(
        category_elements,
        key=lambda value: _numeric_key(value.get("Nb") or ""),
    ):
        number = element.get("Nb") or ""
        categories.append(
            {
                "id": number,
                "name": element.get("Na") or "",
                "kind": int(element.get("Kd", "0")),
                "subcategories": subcategories_by_category.get(number, []),
            }
        )

    payment_elements = [
        element
        for element in root.findall("Payment")
        if element.get("Account") == account_id
    ]
    payments_by_id = _index_by_attribute(payment_elements, "Number")
    payment_methods = [
        {
            "id": element.get("Number") or "",
            "name": element.get("Name") or "",
            "sign": element.get("Sign") or "0",
        }
        for element in sorted(
            payment_elements,
            key=lambda value: _numeric_key(value.get("Number") or ""),
        )
    ]

    total = Decimal("0")
    marked_total = Decimal("0")
    transactions: List[Dict[str, Any]] = []
    for element in root.findall("Transaction"):
        if element.get("Ac") != account_id:
            continue
        attributes = dict(element.attrib)
        transaction_id = attributes.get("Nb") or ""
        amount = _decimal(attributes.get("Am"), "Transaction %s amount" % transaction_id)
        total += amount
        if attributes.get("Ma", "0") == "1":
            marked_total += amount

        party_id = attributes.get("Pa", "0")
        category_id = attributes.get("Ca", "0")
        subcategory_id = attributes.get("Sca", "0")
        payment_id = attributes.get("Pn", "0")
        party = parties_by_id.get(party_id)
        category = categories_by_id.get(category_id)
        subcategory = subcategories_by_key.get((category_id, subcategory_id))
        payment = payments_by_id.get(payment_id)
        protection = _protection(attributes)

        transactions.append(
            {
                "id": transaction_id,
                "date": attributes.get("Dt") or "",
                "valueDate": _nullable(attributes.get("Dv")),
                "amount": attributes.get("Am") or "0",
                "currencyId": attributes.get("Cu") or currency_id,
                "partyId": party_id,
                "partyName": party.get("Na") if party is not None else None,
                "categoryId": category_id,
                "categoryName": category.get("Na") if category is not None else None,
                "subcategoryId": subcategory_id,
                "subcategoryName": subcategory.get("Na") if subcategory is not None else None,
                "paymentMethodId": payment_id,
                "paymentMethodName": payment.get("Name") if payment is not None else None,
                "note": _nullable(attributes.get("No")),
                "paymentReference": _nullable(attributes.get("Pc")),
                "marked": int(attributes.get("Ma", "0")),
                "voucher": _nullable(attributes.get("Vo")),
                "bankReference": _nullable(attributes.get("Ba")),
                "protected": bool(protection),
                "protectionReasons": protection,
                "transferTransactionId": (
                    None if attributes.get("Trt", "0") in ("0", "(null)")
                    else attributes.get("Trt")
                ),
                "splitMotherId": (
                    None if attributes.get("Mo", "0") in ("0", "(null)")
                    else attributes.get("Mo")
                ),
            }
        )

    return {
        "account": {
            "id": account_id,
            "name": account.get("Name") or "",
            "kind": account.get("Kind") or "0",
            "currency": {
                "id": currency_id,
                "name": currency.get("Na") or "",
                "code": currency.get("Ico") or "",
                "symbol": currency.get("Co") or "",
                "precision": precision,
            },
            "totalAmount": _format_decimal(total, precision),
            "totalMarkedAmount": _format_decimal(marked_total, precision),
        },
        "parties": parties,
        "categories": categories,
        "paymentMethods": payment_methods,
        "transactions": transactions,
    }
