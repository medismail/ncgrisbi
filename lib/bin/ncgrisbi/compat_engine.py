from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, List, Mapping, Optional, Tuple

from .errors import MutationConflictError, MutationError, RecordNotFoundError
from .mutations import CreateTransaction, DeleteTransaction, MutationEngine, UpdateTransaction
from .parser import parse_document
from .validator import assert_valid_document
from .writer import LosslessPatchWriter


@dataclass(frozen=True)
class CompatOutcome:
    operation: str
    record_type: str
    record_id: str


@dataclass(frozen=True)
class CompatResult:
    raw_bytes: bytes
    outcomes: Tuple[CompatOutcome, ...]


def _id(value: Any, field: str, allow_zero: bool = True) -> str:
    text = str(value)
    try:
        number = int(text)
    except (ValueError, TypeError):
        raise MutationError("%s must be a numeric Grisbi identifier" % field)
    if number < 0 or (number == 0 and not allow_zero) or str(number) != text:
        raise MutationError("%s is not a canonical Grisbi identifier" % field)
    return text


def _nullable(value: Any) -> str:
    return "(null)" if value is None else str(value)


def _date(value: Any, field: str, allow_null: bool = False) -> str:
    if value is None and allow_null:
        return "(null)"
    if not isinstance(value, str):
        raise MutationError("%s must use MM/DD/YYYY" % field)
    try:
        datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        raise MutationError("%s is not a valid MM/DD/YYYY date" % field)
    return value


def _maps(document: Any):
    root = document.root
    return (
        {
            element.get("Number"): element
            for element in root.findall("Account")
            if element.get("Number")
        },
        {
            element.get("Nb"): element
            for element in root.findall("Currency")
            if element.get("Nb")
        },
        {
            element.get("Number"): element
            for element in root.findall("Payment")
            if element.get("Number")
        },
        {
            element.get("Nb"): element
            for element in root.findall("Party")
            if element.get("Nb")
        },
        {
            element.get("Nb"): element
            for element in root.findall("Category")
            if element.get("Nb")
        },
        {
            (element.get("Nbc"), element.get("Nb")): element
            for element in root.findall("Sub_category")
        },
        {
            element.get("Nb"): element
            for element in root.findall("Transaction")
            if element.get("Nb")
        },
    )


def _amount(value: Any, currency: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MutationError("Amount is not a valid decimal number")
    if not amount.is_finite():
        raise MutationError("Amount must be finite")
    try:
        precision = int(currency.get("Fl", "2"))
    except ValueError:
        raise MutationError("Currency has invalid precision")
    quantum = Decimal(1).scaleb(-precision)
    quantized = amount.quantize(quantum)
    if quantized != amount:
        raise MutationError(
            "Amount has more than %d decimal places" % precision
        )
    return format(quantized, ".%df" % precision)


def _payment(
    payments: Mapping[str, Any],
    account_id: str,
    payment_id: Any,
    amount: str,
    strict: bool = True,
) -> str:
    payment_id = _id(payment_id, "paymentMethodId", allow_zero=True)
    if payment_id == "0":
        return payment_id
    payment = payments.get(payment_id)
    if payment is None:
        raise MutationError("Unknown payment method %s" % payment_id)
    if strict and payment.get("Account") != account_id:
        raise MutationError(
            "Payment method %s does not belong to account %s"
            % (payment_id, account_id)
        )
    if strict:
        decimal = Decimal(amount)
        expected = "1" if decimal < 0 else "2" if decimal > 0 else None
        if expected and payment.get("Sign", "0") not in ("0", expected):
            raise MutationError(
                "Payment method %s has the wrong debit/credit sign" % payment_id
            )
    return payment_id


def _validate_candidate(
    candidate: dict,
    maps: tuple,
    enforce_kind: bool,
    strict_payment: bool,
) -> None:
    accounts, currencies, payments, parties, categories, subcategories, _ = maps
    account_id = candidate["Ac"]
    currency_id = candidate["Cu"]
    account = accounts.get(account_id)
    if account is None:
        raise MutationError("Unknown account %s" % account_id)
    currency = currencies.get(currency_id)
    if currency is None:
        raise MutationError("Unknown currency %s" % currency_id)
    if candidate.get("Exb", "0") == "0" and account.get("Currency") != currency_id:
        raise MutationError("A normal transaction must use its account currency")

    candidate["Am"] = _amount(candidate["Am"], currency)
    party_id = candidate.get("Pa", "0")
    if party_id not in ("0", "(null)") and party_id not in parties:
        raise MutationError("Unknown party %s" % party_id)
    candidate["Pn"] = _payment(
        payments,
        account_id,
        candidate.get("Pn", "0"),
        candidate["Am"],
        strict=strict_payment,
    )

    category_id = candidate.get("Ca", "0")
    subcategory_id = candidate.get("Sca", "0")
    if category_id in ("0", "(null)"):
        if subcategory_id not in ("0", "(null)"):
            raise MutationError("A subcategory cannot be used without a category")
    else:
        category = categories.get(category_id)
        if category is None:
            raise MutationError("Unknown category %s" % category_id)
        if subcategory_id not in ("0", "(null)") and (
            category_id,
            subcategory_id,
        ) not in subcategories:
            raise MutationError(
                "Unknown subcategory %s/%s" % (category_id, subcategory_id)
            )
        if enforce_kind:
            amount = Decimal(candidate["Am"])
            kind = category.get("Kd")
            if amount < 0 and kind != "1":
                raise MutationError("A debit transaction requires a debit category")
            if amount > 0 and kind != "0":
                raise MutationError("A credit transaction requires a credit category")
            if kind == "2":
                raise MutationError(
                    "Special categories are reserved for breakdown transactions"
                )

    if candidate.get("Ma", "0") not in ("0", "1", "2", "3"):
        raise MutationError("Marked state must be between 0 and 3")
    _date(candidate["Dt"], "date")
    if candidate.get("Dv") not in (None, "(null)"):
        _date(candidate["Dv"], "valueDate")


def _update(document: Any, operation: UpdateTransaction, password: Optional[str]):
    assert_valid_document(document)
    maps = _maps(document)
    transaction_id = str(operation.transaction_id)
    existing = maps[-1].get(transaction_id)
    if existing is None:
        raise RecordNotFoundError(
            "Transaction %s does not exist" % transaction_id
        )
    if any(
        existing.get(name, "0") not in ("0", "(null)")
        for name in ("Br", "Trt", "Mo")
    ):
        raise MutationError(
            "Transfer, breakdown and split-child transactions require their dedicated editor"
        )

    changes = dict(operation.changes)
    if not changes:
        raise MutationError("Transaction update must contain changes")
    candidate = dict(existing.attrib)

    if "account_id" in changes:
        candidate["Ac"] = _id(changes["account_id"], "accountId", False)
        account = maps[0].get(candidate["Ac"])
        if account is None:
            raise MutationError("Unknown account %s" % candidate["Ac"])
        if "currency_id" not in changes:
            candidate["Cu"] = account.get("Currency", candidate["Cu"])
    if "currency_id" in changes:
        candidate["Cu"] = _id(changes["currency_id"], "currencyId", False)
    if "date" in changes:
        candidate["Dt"] = _date(changes["date"], "date")
    if "value_date" in changes:
        candidate["Dv"] = _date(changes["value_date"], "valueDate", True)
    if "amount" in changes:
        candidate["Am"] = str(changes["amount"])
    if "party_id" in changes:
        candidate["Pa"] = _id(changes["party_id"], "partyId", True)
    if "category_id" in changes:
        candidate["Ca"] = _id(changes["category_id"], "categoryId", True)
        if "subcategory_id" not in changes:
            candidate["Sca"] = "0"
    if "subcategory_id" in changes:
        candidate["Sca"] = _id(
            changes["subcategory_id"], "subcategoryId", True
        )
    if candidate["Ca"] == "0":
        candidate["Sca"] = "0"

    for field, attribute in (
        ("note", "No"),
        ("payment_reference", "Pc"),
        ("voucher", "Vo"),
        ("bank_reference", "Ba"),
    ):
        if field in changes:
            candidate[attribute] = _nullable(changes[field])
    if "payment_method_id" in changes:
        candidate["Pn"] = _id(
            changes["payment_method_id"], "paymentMethodId", True
        )
    if "marked" in changes:
        candidate["Ma"] = str(changes["marked"])
    for field, attribute in (
        ("financial_year", "Fi"),
        ("budget_id", "Bu"),
        ("subbudget_id", "Sbu"),
    ):
        if field in changes:
            candidate[attribute] = str(changes[field])

    payment_related = {
        "account_id",
        "currency_id",
        "amount",
        "payment_method_id",
    }
    strict_payment = bool(payment_related & set(changes))
    enforce_kind = bool(
        {"amount", "category_id", "subcategory_id"} & set(changes)
    )
    _validate_candidate(candidate, maps, enforce_kind, strict_payment)

    span = document.find_span("Transaction", "Nb", transaction_id)
    if span is None:
        raise MutationError("Transaction byte span is missing")
    writer = LosslessPatchWriter(document)
    writer.replace_record(span, candidate)
    raw_bytes = writer.render(password=password)
    assert_valid_document(parse_document(raw_bytes, password=password))
    return raw_bytes, CompatOutcome(
        "UpdateTransaction", "Transaction", transaction_id
    )


def _delete(document: Any, operation: DeleteTransaction, password: Optional[str]):
    assert_valid_document(document)
    transactions = _maps(document)[-1]
    transaction_id = str(operation.transaction_id)
    existing = transactions.get(transaction_id)
    if existing is None:
        raise RecordNotFoundError(
            "Transaction %s does not exist" % transaction_id
        )
    if any(
        existing.get(name, "0") not in ("0", "(null)")
        for name in ("Br", "Trt", "Mo")
    ):
        raise MutationError(
            "Transfer, breakdown and split-child transactions require their dedicated editor"
        )
    for other_id, other in transactions.items():
        if other_id != transaction_id and (
            other.get("Trt") == transaction_id
            or other.get("Mo") == transaction_id
        ):
            raise MutationError(
                "Transaction %s is referenced by transaction %s"
                % (transaction_id, other_id)
            )

    span = document.find_span("Transaction", "Nb", transaction_id)
    if span is None:
        raise MutationError("Transaction byte span is missing")
    writer = LosslessPatchWriter(document)
    writer.delete(span)
    raw_bytes = writer.render(password=password)
    assert_valid_document(parse_document(raw_bytes, password=password))
    return raw_bytes, CompatOutcome(
        "DeleteTransaction", "Transaction", transaction_id
    )


def _precheck_create(document: Any, operation: Any) -> None:
    if not isinstance(operation, CreateTransaction):
        return
    maps = _maps(document)
    account = maps[0].get(str(operation.account_id))
    if account is None:
        raise MutationError("Unknown account %s" % operation.account_id)
    currency_id = str(operation.currency_id or account.get("Currency"))
    currency = maps[1].get(currency_id)
    if currency is None:
        raise MutationError("Unknown currency %s" % currency_id)
    amount = _amount(operation.amount, currency)
    _payment(
        maps[2],
        str(operation.account_id),
        str(operation.payment_method_id),
        amount,
        strict=True,
    )


def apply_compat_operations(
    document: Any,
    operations: Iterable[Any],
    password: Optional[str] = None,
) -> CompatResult:
    current = document
    raw_bytes = document.raw_bytes
    outcomes: List[CompatOutcome] = []
    touched = set()

    for operation in tuple(operations):
        if isinstance(operation, (UpdateTransaction, DeleteTransaction)):
            transaction_id = str(operation.transaction_id)
            if transaction_id in touched:
                raise MutationConflictError(
                    "Transaction %s is mutated more than once in one batch"
                    % transaction_id
                )
            touched.add(transaction_id)

        if isinstance(operation, UpdateTransaction):
            raw_bytes, outcome = _update(current, operation, password)
            outcomes.append(outcome)
        elif isinstance(operation, DeleteTransaction):
            raw_bytes, outcome = _delete(current, operation, password)
            outcomes.append(outcome)
        else:
            _precheck_create(current, operation)
            result = MutationEngine(current).apply([operation], password=password)
            raw_bytes = result.raw_bytes
            outcome = result.outcomes[0]
            outcomes.append(
                CompatOutcome(
                    outcome.operation,
                    outcome.record_type,
                    outcome.record_id,
                )
            )
        current = parse_document(raw_bytes, password=password)

    return CompatResult(raw_bytes, tuple(outcomes))
