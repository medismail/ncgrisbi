from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .errors import MutationError, RecordNotFoundError
from .model import GsbDocument


ACCOUNT_TYPES = {
    "-1": "BALANCE",
    "0": "BANK",
    "1": "CASH",
    "2": "LIABILITIES",
    "3": "ASSET",
}
_NULLS = (None, "", "0", "(null)", "(NULL)")
_ZERO_TOTAL = {
    "total_amount": Decimal("0"),
    "total_marked_amount": Decimal("0"),
}


class _ReadContext:
    """One-pass direct-child index used by one framed read request."""

    __slots__ = (
        "accounts",
        "account_rows",
        "currencies",
        "payments",
        "payment_rows",
        "parties",
        "party_rows",
        "categories",
        "category_rows",
        "subcategories",
        "subcategory_rows",
        "transactions",
        "transaction_rows",
    )

    def __init__(self, document: GsbDocument):
        self.accounts: Dict[str, Any] = {}
        self.account_rows: List[Any] = []
        self.currencies: Dict[str, Any] = {}
        self.payments: Dict[str, Any] = {}
        self.payment_rows: List[Any] = []
        self.parties: Dict[str, Any] = {}
        self.party_rows: List[Any] = []
        self.categories: Dict[str, Any] = {}
        self.category_rows: List[Any] = []
        self.subcategories: Dict[Tuple[str, str], Any] = {}
        self.subcategory_rows: List[Any] = []
        self.transactions: Dict[str, Any] = {}
        self.transaction_rows: List[Any] = []

        for element in document.root:
            tag = element.tag
            if tag == "Account":
                key = element.get("Number")
                if key:
                    self.accounts[key] = element
                    self.account_rows.append(element)
            elif tag == "Currency":
                key = element.get("Nb")
                if key:
                    self.currencies[key] = element
            elif tag == "Payment":
                key = element.get("Number")
                if key:
                    self.payments[key] = element
                    self.payment_rows.append(element)
            elif tag == "Party":
                key = element.get("Nb")
                if key:
                    self.parties[key] = element
                    self.party_rows.append(element)
            elif tag == "Category":
                key = element.get("Nb")
                if key:
                    self.categories[key] = element
                    self.category_rows.append(element)
            elif tag == "Sub_category":
                parent = element.get("Nbc")
                key = element.get("Nb")
                if parent and key:
                    self.subcategories[(parent, key)] = element
                    self.subcategory_rows.append(element)
            elif tag == "Transaction":
                key = element.get("Nb")
                if key:
                    self.transactions[key] = element
                    self.transaction_rows.append(element)


def _decimal(value: Optional[str], field: str) -> Decimal:
    try:
        result = Decimal(value or "")
    except (InvalidOperation, ValueError) as exc:
        raise MutationError("%s is not a valid decimal number" % field) from exc
    if not result.is_finite():
        raise MutationError("%s must be finite" % field)
    return result


def _numeric(value: Optional[str]) -> int:
    try:
        return int(value or "0")
    except (TypeError, ValueError):
        return 0


def document_info(document: GsbDocument) -> Dict[str, Any]:
    profile = document.format_profile
    if profile is None:
        raise MutationError("The parsed document has no format profile")
    return {
        "fileVersion": document.file_version,
        "grisbiVersion": document.grisbi_version,
        "supportLevel": profile.support_level.value,
        "capabilities": sorted(profile.capabilities),
        "compressed": document.envelope.compressed,
        "encrypted": document.envelope.encrypted,
    }


def list_accounts(document: GsbDocument) -> List[Dict[str, Any]]:
    context = _ReadContext(document)
    totals: Dict[str, Dict[str, Decimal]] = {
        account_id: dict(_ZERO_TOTAL) for account_id in context.accounts
    }
    for transaction in context.transaction_rows:
        account_id = transaction.get("Ac") or ""
        values = totals.get(account_id)
        if values is None:
            continue
        amount = _decimal(
            transaction.get("Am"),
            "Transaction %s amount" % (transaction.get("Nb") or "?"),
        )
        values["total_amount"] += amount
        if transaction.get("Ma", "0") == "1":
            values["total_marked_amount"] += amount

    result: List[Dict[str, Any]] = []
    for account in context.account_rows:
        account_id = account.get("Number") or ""
        currency = context.currencies.get(account.get("Currency") or "")
        values = totals.get(account_id, _ZERO_TOTAL)
        result.append(
            {
                "id": account_id,
                "name": account.get("Name") or "",
                "bank": account.get("Bank") or "0",
                "type": ACCOUNT_TYPES.get(account.get("Kind") or "", "UNKNOWN"),
                "currency": currency.get("Ico") if currency is not None else "Unknown",
                "closed": _numeric(account.get("Closed_account")),
                "total": {
                    "total_amount": float(values["total_amount"]),
                    "total_marked_amount": float(values["total_marked_amount"]),
                },
            }
        )
    return result


def list_categories(document: GsbDocument) -> List[Dict[str, Any]]:
    subcategories: Dict[str, List[Dict[str, str]]] = {}
    for element in document.root.findall("Sub_category"):
        category_id = element.get("Nbc") or ""
        number = element.get("Nb") or ""
        if not category_id or not number:
            continue
        subcategories.setdefault(category_id, []).append(
            {"id": number, "name": element.get("Na") or ""}
        )
    for values in subcategories.values():
        values.sort(key=lambda value: _numeric(value["id"]))

    return [
        {
            "id": element.get("Nb") or "",
            "name": element.get("Na") or "",
            "kind": _numeric(element.get("Kd")),
            "subcategories": subcategories.get(element.get("Nb") or "", []),
        }
        for element in document.root.findall("Category")
        if element.get("Nb")
    ]


def _transfer_target_name(
    transaction: Any,
    transactions: Mapping[str, Any],
    accounts: Mapping[str, Any],
) -> str:
    transfer_id = transaction.get("Trt", "0")
    if transfer_id in _NULLS:
        return ""
    counterpart = transactions.get(transfer_id)
    if counterpart is None or counterpart.get("Trt", "0") != transaction.get("Nb"):
        return ""
    account = accounts.get(counterpart.get("Ac") or "")
    return account.get("Name") if account is not None else ""


def list_parties(document: GsbDocument) -> List[Dict[str, Any]]:
    context = _ReadContext(document)
    result: Dict[str, Dict[str, Any]] = {
        element.get("Nb"): {
            "id": element.get("Nb"),
            "name": element.get("Na") or "",
            "last_amount": 0.0,
            "last_category": "",
            "last_subcategory": "",
            "last_pm": "",
            "last_note": "",
        }
        for element in context.party_rows
    }

    for transaction in context.transaction_rows:
        party_id = transaction.get("Pa") or "0"
        party = result.get(party_id)
        if party is None:
            continue
        transfer_target = _transfer_target_name(
            transaction,
            context.transactions,
            context.accounts,
        )
        if transfer_target:
            party["last_subcategory"] = transfer_target
            continue

        category_id = transaction.get("Ca") or "0"
        subcategory_id = transaction.get("Sca") or "0"
        category = context.categories.get(category_id)
        subcategory = context.subcategories.get((category_id, subcategory_id))
        payment = context.payments.get(transaction.get("Pn") or "0")
        party.update(
            {
                "last_amount": float(
                    _decimal(
                        transaction.get("Am"),
                        "Transaction %s amount" % (transaction.get("Nb") or "?"),
                    )
                ),
                "last_category": (
                    category.get("Na") if category is not None else "Uncategorized"
                ),
                "last_subcategory": (
                    subcategory.get("Na")
                    if subcategory is not None
                    else "Uncategorized"
                ),
                "last_pm": payment.get("Name") if payment is not None else "Unknown",
                "last_note": transaction.get("No"),
            }
        )

    return list(result.values())


def list_transactions(document: GsbDocument, account_id: str) -> Dict[str, Any]:
    context = _ReadContext(document)
    account = context.accounts.get(account_id)
    if account is None:
        raise RecordNotFoundError("Account %s does not exist" % account_id)

    currency_id = account.get("Currency") or ""
    currency = context.currencies.get(currency_id)
    total_amount = Decimal("0")
    total_marked_amount = Decimal("0")
    rows: List[Dict[str, Any]] = []
    maximum_id = 0

    for transaction in context.transaction_rows:
        transaction_id = transaction.get("Nb") or "0"
        maximum_id = max(maximum_id, _numeric(transaction_id))
        if transaction.get("Ac") != account_id:
            continue

        amount = _decimal(
            transaction.get("Am"),
            "Transaction %s amount" % transaction_id,
        )
        total_amount += amount
        if transaction.get("Ma", "0") == "1":
            total_marked_amount += amount

        party = context.parties.get(transaction.get("Pa") or "0")
        payment = context.payments.get(transaction.get("Pn") or "0")
        transfer_id = transaction.get("Trt", "0")
        if transfer_id not in _NULLS:
            category_name = "Transfer"
            subcategory_name = _transfer_target_name(
                transaction,
                context.transactions,
                context.accounts,
            )
        else:
            category_id = transaction.get("Ca") or "0"
            subcategory_id = transaction.get("Sca") or "0"
            category = context.categories.get(category_id)
            subcategory = context.subcategories.get(
                (category_id, subcategory_id)
            )
            category_name = (
                category.get("Na") if category is not None else "Uncategorized"
            )
            subcategory_name = (
                subcategory.get("Na")
                if subcategory is not None
                else "Uncategorized"
            )

        rows.append(
            {
                "Acc": account.get("Name") or "",
                "TxNb": transaction_id,
                "Date": transaction.get("Dt"),
                "Cur": currency.get("Ico") if currency is not None else "Unknown",
                "Am": float(amount),
                "Pa": party.get("Na") if party is not None else "Unknown",
                "Cat": category_name,
                "SCat": subcategory_name,
                "BR": transaction.get("Br"),
                "Note": transaction.get("No"),
                "PM": payment.get("Name") if payment is not None else "Unknown",
                "PMC": transaction.get("Pc"),
                "Ma": _numeric(transaction.get("Ma")),
                "STx": transaction.get("Trt"),
            }
        )

    payment_methods = [
        {"id": element.get("Number"), "name": element.get("Name") or ""}
        for element in context.payment_rows
        if element.get("Account") == account_id
    ]

    return {
        "account_id": account_id,
        "account_name": account.get("Name") or "",
        "bank_id": account.get("Bank") or "0",
        "transactions": rows,
        "currency": {
            "id": currency_id,
            "name": currency.get("Ico") if currency is not None else "Unknown",
        },
        "total_amount": float(total_amount),
        "total_marked_amount": float(total_marked_amount),
        "payment_methods": payment_methods,
        "next_id": maximum_id + 1,
    }


__all__ = [
    "document_info",
    "list_accounts",
    "list_categories",
    "list_parties",
    "list_transactions",
]
