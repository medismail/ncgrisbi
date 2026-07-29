from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .errors import MutationError, RecordNotFoundError
from .parser import parse_document
from .validator import assert_valid_document
from .writer import LosslessPatchWriter

NULLS = ("0", "(null)", None)


@dataclass(frozen=True)
class TransferOutcome:
    operation: str
    record_type: str
    record_id: str
    role: str


@dataclass(frozen=True)
class TransferResult:
    raw_bytes: bytes
    outcomes: Tuple[TransferOutcome, ...]


def _id(value: Any, field: str, allow_zero: bool = False) -> str:
    text = str(value)
    try:
        number = int(text)
    except (ValueError, TypeError):
        raise MutationError("%s must be a numeric Grisbi identifier" % field)
    if number < 0 or (number == 0 and not allow_zero) or str(number) != text:
        raise MutationError("%s is not a canonical Grisbi identifier" % field)
    return text


def _decimal(value: Any, field: str = "amount") -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MutationError("%s is not a valid decimal number" % field)
    if not result.is_finite():
        raise MutationError("%s must be finite" % field)
    return result


def _precision(currency: Any) -> int:
    try:
        precision = int(currency.get("Fl", "2"))
    except ValueError:
        raise MutationError("Currency has invalid precision")
    if precision < 0 or precision > 12:
        raise MutationError("Currency has unsupported precision")
    return precision


def _amount_text(value: Decimal, precision: int) -> str:
    quantum = Decimal(1).scaleb(-precision)
    quantized = value.quantize(quantum)
    if quantized != value:
        raise MutationError(
            "Amount has more than %d decimal places" % precision
        )
    return format(quantized, ".%df" % precision)


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
            for element in root.findall("Transaction")
            if element.get("Nb")
        },
    )


def _next_id(records: Mapping[str, Any]) -> str:
    maximum = 0
    for value in records:
        try:
            maximum = max(maximum, int(value))
        except (ValueError, TypeError):
            continue
    return str(maximum + 1)


def _payment(
    payments: Mapping[str, Any],
    account_id: str,
    payment_id: Any,
    amount: Decimal,
    field: str,
    strict: bool = True,
) -> str:
    payment_id = _id(payment_id, field, allow_zero=True)
    if payment_id == "0":
        return "0"
    payment = payments.get(payment_id)
    if payment is None:
        raise MutationError("Unknown payment method %s" % payment_id)
    if strict and payment.get("Account") != account_id:
        raise MutationError(
            "Payment method %s does not belong to account %s"
            % (payment_id, account_id)
        )
    sign = payment.get("Sign", "0")
    expected = "1" if amount < 0 else "2" if amount > 0 else None
    if strict and expected and sign not in ("0", expected):
        raise MutationError(
            "Payment method %s has the wrong debit/credit sign" % payment_id
        )
    return payment_id


def _nullable(value: Any) -> str:
    return "(null)" if value is None or str(value) == "" else str(value)


def _date(value: Any, field: str = "date") -> str:
    text = str(value)
    import datetime

    try:
        datetime.datetime.strptime(text, "%m/%d/%Y")
    except ValueError:
        raise MutationError(
            "%s must use a valid MM/DD/YYYY date" % field
        )
    return text


def _party(
    writer: LosslessPatchWriter,
    parties: Dict[str, Any],
    raw: Mapping[str, Any],
    outcomes: List[TransferOutcome],
) -> str:
    if raw.get("partyId") not in (None, "", "0", 0):
        party_id = _id(raw["partyId"], "partyId", allow_zero=True)
        if party_id != "0" and party_id not in parties:
            raise MutationError("Unknown party %s" % party_id)
        return party_id

    name = str(raw.get("partyName") or "").strip()
    if not name:
        return "0"
    key = " ".join(name.split()).casefold()
    matches = [
        (party_id, element)
        for party_id, element in parties.items()
        if " ".join((element.get("Na") or "").split()).casefold() == key
    ]
    if len(matches) > 1:
        raise MutationError("Party %s is ambiguous" % name)
    if matches:
        return matches[0][0]
    if raw.get("createMissing") is not True:
        raise MutationError("Party %s does not exist" % name)

    party_id = _next_id(parties)
    attributes = {
        "Nb": party_id,
        "Na": name,
        "Txt": "(null)",
        "Search": "(null)",
        "IgnCase": "0",
        "UseRegex": "0",
    }
    writer.insert_record("Party", attributes)
    parties[party_id] = type(
        "PartyProxy", (), {"get": attributes.get}
    )()
    outcomes.append(
        TransferOutcome("CreateParty", "Party", party_id, "party")
    )
    return party_id


def _base_attributes(
    account_id: str,
    transaction_id: str,
    currency_id: str,
    amount: str,
    raw: Mapping[str, Any],
    party_id: str,
    payment_id: str,
) -> dict:
    return {
        "Ac": account_id,
        "Nb": transaction_id,
        "Id": "(null)",
        "Dt": _date(raw.get("date")),
        "Dv": _nullable(raw.get("valueDate")),
        "Cu": currency_id,
        "Am": amount,
        "Exb": "0",
        "Exr": "0.00",
        "Exf": "0.00",
        "Pa": party_id,
        "Ca": "0",
        "Sca": "0",
        "Br": "0",
        "No": _nullable(raw.get("note")),
        "Pn": payment_id,
        "Pc": _nullable(raw.get("paymentReference")),
        "Ma": str(raw.get("marked", 0)),
        "Ar": "0",
        "Au": "0",
        "Re": "0",
        "Fi": str(raw.get("financialYear", "0")),
        "Bu": str(raw.get("budgetId", "0")),
        "Sbu": str(raw.get("subbudgetId", "0")),
        "Vo": _nullable(raw.get("voucher")),
        "Ba": _nullable(raw.get("bankReference")),
        "Trt": "0",
        "Mo": "0",
    }


def create_transfer(
    document: Any,
    raw: Mapping[str, Any],
    password: Optional[str] = None,
) -> TransferResult:
    assert_valid_document(document)
    accounts, currencies, payments, parties, transactions = _maps(document)
    source_account_id = _id(raw.get("accountId"), "accountId")
    target_account_id = _id(raw.get("targetAccountId"), "targetAccountId")
    if source_account_id == target_account_id:
        raise MutationError("Transfer destination must be a different account")
    source_account = accounts.get(source_account_id)
    target_account = accounts.get(target_account_id)
    if source_account is None or target_account is None:
        raise MutationError("Unknown transfer account")
    source_currency_id = source_account.get("Currency")
    target_currency_id = target_account.get("Currency")
    if source_currency_id != target_currency_id:
        raise MutationError(
            "Cross-currency transfers are not yet safely editable"
        )
    currency = currencies.get(source_currency_id)
    if currency is None:
        raise MutationError("Transfer account currency is missing")

    precision = _precision(currency)
    amount = _decimal(raw.get("amount"))
    if amount == 0:
        raise MutationError("Transfer amount cannot be zero")
    amount_text = _amount_text(amount, precision)
    counterpart_amount = _amount_text(-amount, precision)
    source_payment = _payment(
        payments,
        source_account_id,
        raw.get("paymentMethodId", "0"),
        amount,
        "paymentMethodId",
    )
    target_payment = _payment(
        payments,
        target_account_id,
        raw.get("targetPaymentMethodId", "0"),
        -amount,
        "targetPaymentMethodId",
    )

    writer = LosslessPatchWriter(document)
    outcomes: List[TransferOutcome] = []
    party_id = _party(writer, parties, raw, outcomes)
    source_id = _next_id(transactions)
    transactions[source_id] = None
    counterpart_id = _next_id(transactions)

    source = _base_attributes(
        source_account_id,
        source_id,
        source_currency_id,
        amount_text,
        raw,
        party_id,
        source_payment,
    )
    source["Trt"] = counterpart_id
    counterpart = dict(source)
    counterpart.update(
        {
            "Ac": target_account_id,
            "Nb": counterpart_id,
            "Am": counterpart_amount,
            "Pn": target_payment,
            "Pc": _nullable(raw.get("targetPaymentReference")),
            "Ma": "0",
            "Re": "0",
            "Trt": source_id,
        }
    )

    writer.insert_record("Transaction", source)
    writer.insert_record("Transaction", counterpart)
    raw_bytes = writer.render(password=password)
    assert_valid_document(parse_document(raw_bytes, password=password))
    outcomes.extend(
        [
            TransferOutcome(
                "CreateTransfer", "Transaction", source_id, "source"
            ),
            TransferOutcome(
                "CreateTransfer",
                "Transaction",
                counterpart_id,
                "counterpart",
            ),
        ]
    )
    return TransferResult(raw_bytes, tuple(outcomes))


def _pair(document: Any, transaction_id: Any):
    _, _, _, _, transactions = _maps(document)
    transaction_id = _id(transaction_id, "transactionId")
    source = transactions.get(transaction_id)
    if source is None:
        raise RecordNotFoundError(
            "Transaction %s does not exist" % transaction_id
        )
    if source.get("Br", "0") not in ("0", "(null)") or source.get(
        "Mo", "0"
    ) not in ("0", "(null)"):
        raise MutationError(
            "Breakdown or split-child transaction requires its dedicated editor"
        )
    counterpart_id = source.get("Trt", "0")
    counterpart = transactions.get(counterpart_id)
    if (
        counterpart_id in ("0", "(null)")
        or counterpart is None
        or counterpart.get("Trt", "0") != transaction_id
    ):
        raise MutationError("Transaction is not a valid reciprocal transfer")
    if source.get("Cu") != counterpart.get("Cu"):
        raise MutationError(
            "Cross-currency transfers are not yet safely editable"
        )
    return transaction_id, source, counterpart_id, counterpart


def update_transfer(
    document: Any,
    raw: Mapping[str, Any],
    password: Optional[str] = None,
) -> TransferResult:
    assert_valid_document(document)
    source_id, source, counterpart_id, counterpart = _pair(
        document, raw.get("transactionId")
    )
    accounts, currencies, payments, parties, transactions = _maps(document)
    changes = raw.get("changes")
    if not isinstance(changes, Mapping) or not changes:
        raise MutationError("Transfer update requires changes")

    source_attributes = dict(source.attrib)
    old_counterpart = dict(counterpart.attrib)
    target_account_id = str(
        changes.get("targetAccountId", counterpart.get("Ac"))
    )
    if target_account_id == source_attributes["Ac"]:
        raise MutationError("Transfer destination must be different")
    target_account = accounts.get(target_account_id)
    if target_account is None:
        raise MutationError(
            "Unknown target account %s" % target_account_id
        )
    if target_account.get("Currency") != source_attributes["Cu"]:
        raise MutationError(
            "Cross-currency transfers are not yet safely editable"
        )

    if "date" in changes:
        source_attributes["Dt"] = _date(changes["date"])
    if "amount" in changes:
        amount = _decimal(changes["amount"])
        source_attributes["Am"] = _amount_text(
            amount,
            _precision(currencies[source_attributes["Cu"]]),
        )
    amount = _decimal(source_attributes["Am"])
    if amount == 0:
        raise MutationError("Transfer amount cannot be zero")
    if "partyId" in changes:
        party_id = _id(changes["partyId"], "partyId", allow_zero=True)
        if party_id != "0" and party_id not in parties:
            raise MutationError("Unknown party %s" % party_id)
        source_attributes["Pa"] = party_id
    for field, attribute in (
        ("note", "No"),
        ("voucher", "Vo"),
        ("bankReference", "Ba"),
    ):
        if field in changes:
            source_attributes[attribute] = _nullable(changes[field])
    if "paymentReference" in changes:
        source_attributes["Pc"] = _nullable(changes["paymentReference"])
    if "marked" in changes:
        source_attributes["Ma"] = str(changes["marked"])
    if "paymentMethodId" in changes:
        source_attributes["Pn"] = str(changes["paymentMethodId"])

    source_strict = bool({"amount", "paymentMethodId"} & set(changes))
    source_attributes["Pn"] = _payment(
        payments,
        source_attributes["Ac"],
        source_attributes.get("Pn", "0"),
        amount,
        "paymentMethodId",
        strict=source_strict,
    )

    writer = LosslessPatchWriter(document)
    source_span = document.find_span("Transaction", "Nb", source_id)
    counterpart_span = document.find_span(
        "Transaction", "Nb", counterpart_id
    )
    if source_span is None or counterpart_span is None:
        raise MutationError("Transfer byte spans are missing")

    target_changed = target_account_id != counterpart.get("Ac")
    precision = _precision(currencies[source_attributes["Cu"]])
    if target_changed:
        new_counterpart_id = _next_id(transactions)
        source_attributes["Trt"] = new_counterpart_id
        target_payment = _payment(
            payments,
            target_account_id,
            changes.get("targetPaymentMethodId", "0"),
            -amount,
            "targetPaymentMethodId",
        )
        new_counterpart = dict(source_attributes)
        new_counterpart.update(
            {
                "Ac": target_account_id,
                "Nb": new_counterpart_id,
                "Am": _amount_text(-amount, precision),
                "Pn": target_payment,
                "Pc": _nullable(changes.get("targetPaymentReference")),
                "Ma": "0",
                "Re": "0",
                "Trt": source_id,
            }
        )
        writer.replace_record(source_span, source_attributes)
        writer.delete(counterpart_span)
        writer.insert_record("Transaction", new_counterpart)
        saved_counterpart_id = new_counterpart_id
    else:
        counterpart_attributes = dict(old_counterpart)
        # Grisbi copies common fields but preserves counterpart-specific value
        # date, payment/content, marked state and reconciliation metadata.
        for attribute in (
            "Dt",
            "Pa",
            "No",
            "Vo",
            "Ba",
            "Exb",
            "Exr",
            "Exf",
            "Fi",
            "Bu",
            "Sbu",
        ):
            counterpart_attributes[attribute] = source_attributes[attribute]
        counterpart_attributes["Ca"] = "0"
        counterpart_attributes["Sca"] = "0"
        counterpart_attributes["Br"] = "0"
        counterpart_attributes["Mo"] = "0"
        counterpart_attributes["Am"] = _amount_text(-amount, precision)
        if "targetPaymentMethodId" in changes:
            counterpart_attributes["Pn"] = str(
                changes["targetPaymentMethodId"]
            )
        target_strict = bool(
            {"amount", "targetAccountId", "targetPaymentMethodId"}
            & set(changes)
        )
        counterpart_attributes["Pn"] = _payment(
            payments,
            target_account_id,
            counterpart_attributes.get("Pn", "0"),
            -amount,
            "targetPaymentMethodId",
            strict=target_strict,
        )
        if "targetPaymentReference" in changes:
            counterpart_attributes["Pc"] = _nullable(
                changes["targetPaymentReference"]
            )
        writer.replace_record(source_span, source_attributes)
        writer.replace_record(counterpart_span, counterpart_attributes)
        saved_counterpart_id = counterpart_id

    raw_bytes = writer.render(password=password)
    assert_valid_document(parse_document(raw_bytes, password=password))
    return TransferResult(
        raw_bytes,
        (
            TransferOutcome(
                "UpdateTransfer", "Transaction", source_id, "source"
            ),
            TransferOutcome(
                "UpdateTransfer",
                "Transaction",
                saved_counterpart_id,
                "counterpart",
            ),
        ),
    )


def delete_transfer(
    document: Any,
    raw: Mapping[str, Any],
    password: Optional[str] = None,
) -> TransferResult:
    assert_valid_document(document)
    source_id, _source, counterpart_id, _counterpart = _pair(
        document, raw.get("transactionId")
    )
    writer = LosslessPatchWriter(document)
    source_span = document.find_span("Transaction", "Nb", source_id)
    counterpart_span = document.find_span(
        "Transaction", "Nb", counterpart_id
    )
    if source_span is None or counterpart_span is None:
        raise MutationError("Transfer byte spans are missing")
    writer.delete(source_span)
    writer.delete(counterpart_span)
    raw_bytes = writer.render(password=password)
    assert_valid_document(parse_document(raw_bytes, password=password))
    return TransferResult(
        raw_bytes,
        (
            TransferOutcome(
                "DeleteTransfer", "Transaction", source_id, "source"
            ),
            TransferOutcome(
                "DeleteTransfer",
                "Transaction",
                counterpart_id,
                "counterpart",
            ),
        ),
    )


def apply_transfer(
    document: Any,
    raw: Mapping[str, Any],
    password: Optional[str] = None,
) -> TransferResult:
    operation_type = raw.get("type")
    if operation_type == "createTransfer":
        return create_transfer(document, raw, password)
    if operation_type == "updateTransfer":
        return update_transfer(document, raw, password)
    if operation_type == "deleteTransfer":
        return delete_transfer(document, raw, password)
    raise MutationError(
        "Unsupported transfer operation %s" % operation_type
    )
