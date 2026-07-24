from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

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


def _by_attribute(elements: Iterable[Any], attribute: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for element in elements:
        value = element.get(attribute)
        if value is not None:
            result[value] = element
    return result


def _decimal(value: Optional[str], field: str) -> Decimal:
    try:
        result = Decimal(value or "")
    except Exception as exc:
        raise MutationError("%s is not a valid decimal number" % field) from exc
    if not result.is_finite():
        raise MutationError("%s must be finite" % field)
    return result


def _numeric(value: Optional[str]) -> int:
    try:
        return int(value or "0")
    except (TypeError, ValueError):
        return 0


def _maps(document: GsbDocument) -> Dict[str, Any]:
    root = document.root
    accounts = _by_attribute(root.findall("Account"), "Number")
    currencies = _by_attribute(root.findall("Currency"), "Nb")
    banks = _by_attribute(root.findall("Bank"), "Nb")
    payments = _by_attribute(root.findall("Payment"), "Number")
    parties = _by_attribute(root.findall("Party"), "Nb")
    categories = _by_attribute(root.findall("Category"), "Nb")
    subcategories = {
        (element.get("Nbc") or "", element.get("Nb") or ""): element
        for element in root.findall("Sub_category")
    }
    transactions = _by_attribute(root.findall("Transaction"), "Nb")
    return {
        "accounts": accounts,
        "currencies": currencies,
        "banks": banks,
        "payments": payments,
        "parties": parties,
        "categories": categories,
        "subcategories": subcategories,
        "transactions": transactions,
    }


def _account_totals(document: GsbDocument) -> Dict[str, Dict[str, Decimal]]:
    totals: Dict[str, Dict[str, Decimal]] = {
        element.get("Number"): {
            "total_amount": Decimal("0"),
            "total_marked_amount": Decimal("0"),
        }
        for element in document.root.findall("Account")
        if element.get("Number")
    }
    for transaction in document.root.findall("Transaction"):
        account_id = transaction.get("Ac") or ""
        if account_id not in totals:
            continue
        amount = _decimal(
            transaction.get("Am"),
            "Transaction %s amount" % (transaction.get("Nb") or "?"),
        )
        totals[account_id]["total_amount"] += amount
        if transaction.get("Ma", "0") == "1":
            totals[account_id]["total_marked_amount"] += amount
    return totals


def document_info(document: GsbDocument) -> Dict[str, Any]:
    return {
        "fileVersion": document.file_version,
        "grisbiVersion": document.grisbi_version,
        "supportLevel": document.format_profile.support_level.value,
        "capabilities": sorted(document.format_profile.capabilities),
        "compressed": document.envelope.compressed,
        "encrypted": document.envelope.encrypted,
    }


def list_accounts(document: GsbDocument) -> List[Dict[str, Any]]:
    maps = _maps(document)
    totals = _account_totals(document)
    result: List[Dict[str, Any]] = []
    for account in document.root.findall("Account"):
        account_id = account.get("Number")
        if not account_id:
            continue
        currency = maps["currencies"].get(account.get("Currency") or "")
        values = totals.get(
            account_id,
            {
                "total_amount": Decimal("0"),
                "total_marked_amount": Decimal("0"),
            },
        )
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
    maps = _maps(document)
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
        for element in document.root.findall("Party")
        if element.get("Nb")
    }

    for transaction in document.root.findall("Transaction"):
        party_id = transaction.get("Pa") or "0"
        party = result.get(party_id)
        if party is None:
            continue
        transfer_target = _transfer_target_name(
            transaction,
            maps["transactions"],
            maps["accounts"],
        )
        if transfer_target:
            party["last_subcategory"] = transfer_target
            continue

        category_id = transaction.get("Ca") or "0"
        subcategory_id = transaction.get("Sca") or "0"
        category = maps["categories"].get(category_id)
        subcategory = maps["subcategories"].get((category_id, subcategory_id))
        payment = maps["payments"].get(transaction.get("Pn") or "0")
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
    maps = _maps(document)
    account = maps["accounts"].get(account_id)
    if account is None:
        raise RecordNotFoundError("Account %s does not exist" % account_id)

    currency_id = account.get("Currency") or ""
    currency = maps["currencies"].get(currency_id)
    totals = _account_totals(document).get(
        account_id,
        {
            "total_amount": Decimal("0"),
            "total_marked_amount": Decimal("0"),
        },
    )
    rows: List[Dict[str, Any]] = []
    maximum_id = 0

    for transaction in document.root.findall("Transaction"):
        transaction_id = transaction.get("Nb") or "0"
        maximum_id = max(maximum_id, _numeric(transaction_id))
        if transaction.get("Ac") != account_id:
            continue

        party = maps["parties"].get(transaction.get("Pa") or "0")
        payment = maps["payments"].get(transaction.get("Pn") or "0")
        transfer_id = transaction.get("Trt", "0")
        if transfer_id not in _NULLS:
            category_name = "Transfer"
            subcategory_name = _transfer_target_name(
                transaction,
                maps["transactions"],
                maps["accounts"],
            )
        else:
            category_id = transaction.get("Ca") or "0"
            subcategory_id = transaction.get("Sca") or "0"
            category = maps["categories"].get(category_id)
            subcategory = maps["subcategories"].get(
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
                "Am": float(
                    _decimal(
                        transaction.get("Am"),
                        "Transaction %s amount" % transaction_id,
                    )
                ),
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
        for element in document.root.findall("Payment")
        if element.get("Number") and element.get("Account") == account_id
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
        "total_amount": float(totals["total_amount"]),
        "total_marked_amount": float(totals["total_marked_amount"]),
        "payment_methods": payment_methods,
        "next_id": maximum_id + 1,
    }
