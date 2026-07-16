from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .errors import MutationError, RecordNotFoundError
from .validator import warning_issues

_NULL_VALUES = (None, "(null)", "(NULL)")

# Transaction flag bits used by the compact wire format.
TX_BREAKDOWN = 1
TX_SPLIT_CHILD = 2
TX_TRANSFER = 4
TX_BROKEN_TRANSFER = 8
TX_CROSS_CURRENCY = 16


def _nullable(value: Optional[str]) -> Optional[str]:
    return None if value in _NULL_VALUES else value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _canonical_positive_id(value: Any, field: str) -> str:
    text = str(value)
    try:
        number = int(text)
    except (TypeError, ValueError):
        raise MutationError("%s must be a numeric Grisbi identifier" % field)
    if number <= 0 or str(number) != text:
        raise MutationError(
            "%s is not a canonical positive Grisbi identifier" % field
        )
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


def _index_by_attribute(
    elements: Iterable[Any],
    attribute: str,
) -> Dict[str, Any]:
    indexed: Dict[str, Any] = {}
    for element in elements:
        key = element.get(attribute)
        if key is not None:
            indexed[key] = element
    return indexed


def _payment_sign_matches(payment: Any, amount: Decimal) -> bool:
    if payment is None or amount == 0:
        return True
    sign = payment.get("Sign", "0")
    return sign == "0" or (amount < 0 and sign == "1") or (
        amount > 0 and sign == "2"
    )


def _mapped_payment_id(
    source_payment: Any,
    current_account_id: str,
    payments_by_account: Mapping[str, List[Any]],
    amount: Decimal,
) -> str:
    if source_payment is None:
        return "0"
    if (
        source_payment.get("Account") == current_account_id
        and _payment_sign_matches(source_payment, amount)
    ):
        return source_payment.get("Number") or "0"
    name = (source_payment.get("Name") or "").casefold()
    for candidate in payments_by_account.get(current_account_id, []):
        if (
            (candidate.get("Name") or "").casefold() == name
            and _payment_sign_matches(candidate, amount)
        ):
            return candidate.get("Number") or "0"
    return "0"


def build_account_snapshot(document: Any, account_id: Any) -> Dict[str, Any]:
    """Build the compact Phase 6 account snapshot.

    The optional ``U`` array carries Grisbi's saved transaction-view preferences.
    The UI may honour these in the responsive phase without expanding every row.
    ``W`` contains non-fatal compatibility warnings, such as damaged transfer
    links; affected transactions remain visible but read-only.
    """
    account_id = _canonical_positive_id(account_id, "accountId")
    root = document.root
    general = root.find("General")

    account_elements = list(root.findall("Account"))
    accounts_by_id = _index_by_attribute(account_elements, "Number")
    account = accounts_by_id.get(account_id)
    if account is None:
        raise RecordNotFoundError("Account %s does not exist" % account_id)

    currencies = _index_by_attribute(root.findall("Currency"), "Nb")
    currency_id = account.get("Currency") or ""
    currency = currencies.get(currency_id)
    if currency is None:
        raise MutationError(
            "Account %s references missing currency %s"
            % (account_id, currency_id)
        )
    precision = _safe_int(currency.get("Fl", "2"), 2)
    if precision < 0 or precision > 12:
        raise MutationError(
            "Currency %s has unsupported precision" % currency_id
        )

    party_elements = list(root.findall("Party"))
    parties = [
        [element.get("Nb") or "", element.get("Na") or ""]
        for element in sorted(
            party_elements,
            key=lambda element: _numeric_key(element.get("Nb") or ""),
        )
    ]

    category_elements = list(root.findall("Category"))
    subcategories_by_category: Dict[str, List[List[str]]] = {}
    for element in root.findall("Sub_category"):
        category_number = element.get("Nbc") or ""
        number = element.get("Nb") or ""
        subcategories_by_category.setdefault(category_number, []).append(
            [number, element.get("Na") or ""]
        )
    for values in subcategories_by_category.values():
        values.sort(key=lambda item: _numeric_key(item[0]))

    categories: List[List[Any]] = []
    for element in sorted(
        category_elements,
        key=lambda value: _numeric_key(value.get("Nb") or ""),
    ):
        number = element.get("Nb") or ""
        categories.append(
            [
                number,
                element.get("Na") or "",
                _safe_int(element.get("Kd", "0")),
                subcategories_by_category.get(number, []),
            ]
        )

    # Grisbi payment numbers are global identifiers. Account is a property used
    # by the form to filter choices, not part of the payment identity.
    payment_elements = list(root.findall("Payment"))
    payments_by_id = _index_by_attribute(payment_elements, "Number")
    payments_by_account: Dict[str, List[Any]] = {}
    for element in payment_elements:
        payments_by_account.setdefault(element.get("Account") or "", []).append(
            element
        )
    payment_groups: List[List[Any]] = []
    for payment_account, values in sorted(
        payments_by_account.items(),
        key=lambda item: _numeric_key(item[0]),
    ):
        values = sorted(
            values,
            key=lambda value: _numeric_key(value.get("Number") or ""),
        )
        payment_groups.append(
            [
                payment_account,
                [
                    [
                        element.get("Number") or "",
                        element.get("Name") or "",
                        _safe_int(element.get("Sign", "0")),
                        _safe_int(element.get("Show_entry", "0")),
                        _safe_int(element.get("Automatic_number", "0")),
                        _nullable(element.get("Current_number")),
                    ]
                    for element in values
                ],
            ]
        )

    accounts: List[List[Any]] = []
    for element in sorted(
        account_elements,
        key=lambda value: _numeric_key(value.get("Number") or ""),
    ):
        accounts.append(
            [
                element.get("Number") or "",
                element.get("Name") or "",
                _safe_int(element.get("Kind", "0")),
                element.get("Currency") or "",
                element.get("Default_debit_method") or "0",
                element.get("Default_credit_method") or "0",
                _safe_int(element.get("Closed_account", "0")),
            ]
        )

    transaction_elements = list(root.findall("Transaction"))
    transactions_by_id = _index_by_attribute(transaction_elements, "Nb")
    total = Decimal("0")
    marked_total = Decimal("0")
    transactions: List[List[Any]] = []
    for element in transaction_elements:
        if element.get("Ac") != account_id:
            continue
        attributes = dict(element.attrib)
        transaction_id = attributes.get("Nb") or ""
        amount = _decimal(
            attributes.get("Am"),
            "Transaction %s amount" % transaction_id,
        )
        total += amount
        if attributes.get("Ma", "0") == "1":
            marked_total += amount

        transfer_id = attributes.get("Trt", "0")
        target_account_id: Optional[str] = None
        target_payment_id: Optional[str] = None
        flags = 0
        if attributes.get("Br", "0") not in ("0", "(null)"):
            flags |= TX_BREAKDOWN
        if attributes.get("Mo", "0") not in ("0", "(null)"):
            flags |= TX_SPLIT_CHILD
        if transfer_id not in ("0", "(null)"):
            counterpart = transactions_by_id.get(transfer_id)
            if (
                counterpart is None
                or counterpart.get("Trt", "0") != transaction_id
            ):
                flags |= TX_BROKEN_TRANSFER
            else:
                flags |= TX_TRANSFER
                target_account_id = counterpart.get("Ac") or None
                target_payment_id = counterpart.get("Pn") or "0"
                if counterpart.get("Cu") != attributes.get("Cu"):
                    flags |= TX_CROSS_CURRENCY

        transactions.append(
            [
                transaction_id,
                attributes.get("Dt") or "",
                _nullable(attributes.get("Dv")),
                attributes.get("Am") or "0",
                attributes.get("Pa", "0"),
                attributes.get("Ca", "0"),
                attributes.get("Sca", "0"),
                attributes.get("Pn", "0"),
                _nullable(attributes.get("No")),
                _nullable(attributes.get("Pc")),
                _safe_int(attributes.get("Ma", "0")),
                _nullable(attributes.get("Vo")),
                _nullable(attributes.get("Ba")),
                attributes.get("Br", "0"),
                None if transfer_id in ("0", "(null)") else transfer_id,
                _nullable(attributes.get("Mo")),
                flags,
                target_account_id,
                target_payment_id,
            ]
        )

    # Grisbi completion prefers the last payee transaction in the current
    # account, then the last one in another account. Split children are ignored.
    current_history: Dict[str, Any] = {}
    other_history: Dict[str, Any] = {}
    for element in transaction_elements:
        party_id = element.get("Pa", "0")
        if party_id in ("0", "(null)") or element.get("Mo", "0") not in (
            "0",
            "(null)",
        ):
            continue
        if element.get("Ac") == account_id:
            current_history[party_id] = element
        else:
            other_history[party_id] = element

    histories: List[List[Any]] = []
    for party_id in sorted(
        set(current_history) | set(other_history),
        key=_numeric_key,
    ):
        element = current_history.get(party_id) or other_history.get(party_id)
        if element is None:
            continue
        amount = _decimal(element.get("Am"), "Completion amount")
        source_payment = payments_by_id.get(element.get("Pn", "0"))
        mapped_payment = _mapped_payment_id(
            source_payment,
            account_id,
            payments_by_account,
            amount,
        )
        target_account = None
        transfer_id = element.get("Trt", "0")
        if transfer_id not in ("0", "(null)"):
            counterpart = transactions_by_id.get(transfer_id)
            if (
                counterpart is not None
                and counterpart.get("Trt", "0") == element.get("Nb")
            ):
                target_account = counterpart.get("Ac")
        histories.append(
            [
                party_id,
                element.get("Ac") or "",
                element.get("Am") or "0",
                element.get("Ca", "0"),
                element.get("Sca", "0"),
                mapped_payment,
                _nullable(element.get("No")),
                _nullable(element.get("Pc")),
                _nullable(element.get("Vo")),
                _nullable(element.get("Ba")),
                target_account,
            ]
        )

    preferences = [
        max(1, min(3, _safe_int(account.get("Lines_per_transaction", "1"), 1))),
        _safe_int(general.get("Two_lines_showed", "0") if general is not None else 0),
        _safe_int(general.get("Three_lines_showed", "0") if general is not None else 0),
        general.get("Transactions_view", "") if general is not None else "",
        general.get("Transaction_column_width", "") if general is not None else "",
        account.get("Sorting_kind_column") or "",
    ]
    warnings = [
        [issue.code, issue.message, issue.tag, issue.record_id]
        for issue in warning_issues(document)
    ]

    return {
        "v": 2,
        "a": [
            account_id,
            account.get("Name") or "",
            _safe_int(account.get("Kind", "0")),
            currency_id,
            currency.get("Na") or "",
            currency.get("Ico") or "",
            currency.get("Co") or "",
            precision,
            _format_decimal(total, precision),
            _format_decimal(marked_total, precision),
        ],
        "A": accounts,
        "P": parties,
        "C": categories,
        "M": payment_groups,
        "T": transactions,
        "H": histories,
        "U": preferences,
        "W": warnings,
    }
