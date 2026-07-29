from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .envelope import encode_envelope
from .errors import (
    ConfirmationRequiredError,
    MarkStateError,
    MutationConflictError,
    MutationError,
    RecordNotFoundError,
)
from .parser import parse_document
from .validator import assert_valid_document, warning_issues
from .writer import LosslessPatchWriter

NULLS = (None, "", "0", "(null)", "(NULL)")
_WS_RE = re.compile(r"\s+", re.UNICODE)


@dataclass(frozen=True)
class Phase6Result:
    raw_bytes: bytes
    outcomes: Tuple[Dict[str, Any], ...]
    warnings: Tuple[Dict[str, Any], ...]
    changed_records: int


def _canonical_id(value: Any, field: str, allow_zero: bool = False) -> str:
    text = str(value)
    try:
        number = int(text)
    except (ValueError, TypeError):
        raise MutationError("%s must be a numeric Grisbi identifier" % field)
    if number < 0 or (number == 0 and not allow_zero) or str(number) != text:
        raise MutationError("%s is not a canonical Grisbi identifier" % field)
    return text


def _nullable(value: Any) -> str:
    return "(null)" if value is None or str(value) == "" else str(value)


def _date(value: Any, field: str = "date", allow_null: bool = False) -> str:
    if value is None and allow_null:
        return "(null)"
    if not isinstance(value, str):
        raise MutationError("%s must use MM/DD/YYYY" % field)
    try:
        datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        raise MutationError("%s must use a valid MM/DD/YYYY date" % field)
    return value


def _decimal(value: Any, field: str = "amount") -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MutationError("%s is not a valid decimal number" % field)
    if not result.is_finite():
        raise MutationError("%s must be finite" % field)
    return result


def _precision(currency: Mapping[str, str]) -> int:
    try:
        value = int(currency.get("Fl", "2"))
    except ValueError:
        raise MutationError("Currency has invalid precision")
    if value < 0 or value > 12:
        raise MutationError("Currency has unsupported precision")
    return value


def _amount_text(value: Any, currency: Mapping[str, str]) -> str:
    amount = _decimal(value)
    precision = _precision(currency)
    quantum = Decimal(1).scaleb(-precision)
    try:
        quantized = amount.quantize(quantum)
    except InvalidOperation:
        raise MutationError("Amount cannot be represented in the account currency")
    if quantized != amount:
        raise MutationError("Amount has more than %d decimal places" % precision)
    return format(quantized, ".%df" % precision)


def _clean_name(value: Any, record_type: str) -> str:
    if not isinstance(value, str):
        raise MutationError("%s name must be text" % record_type)
    value = _WS_RE.sub(" ", unicodedata.normalize("NFKC", value)).strip()
    if not value:
        raise MutationError("%s name cannot be empty" % record_type)
    if any(ord(char) < 32 for char in value):
        raise MutationError("%s name contains an unsupported control character" % record_type)
    return value


def _name_key(value: Any, record_type: str) -> str:
    return _clean_name(value, record_type).casefold()


def _strict_fields(raw: Mapping[str, Any], allowed: Sequence[str]) -> None:
    unknown = sorted(set(raw) - set(allowed) - {"type"})
    if unknown:
        raise MutationError(
            "%s contains unsupported fields: %s"
            % (raw.get("type", "operation"), ", ".join(unknown))
        )


def _required(raw: Mapping[str, Any], field: str) -> Any:
    if field not in raw:
        raise MutationError("%s requires %s" % (raw.get("type", "operation"), field))
    return raw[field]


def _bool(raw: Mapping[str, Any], field: str, default: bool = False) -> bool:
    if field not in raw:
        return default
    value = raw[field]
    if not isinstance(value, bool):
        raise MutationError("%s must be a JSON boolean" % field)
    return value


def _is_reconciled(attributes: Mapping[str, str]) -> bool:
    # Grisbi explicitly says Ma must be checked before Re. Re can remain populated
    # after Ctrl+R changes a transaction back from reconciled state.
    return attributes.get("Ma", "0") == "3"


class Phase6Session:
    def __init__(self, document: Any):
        assert_valid_document(document)
        self.document = document
        self.accounts: Dict[str, Dict[str, str]] = {}
        self.currencies: Dict[str, Dict[str, str]] = {}
        self.payments: Dict[str, Dict[str, str]] = {}
        self.parties: Dict[str, Dict[str, str]] = {}
        self.categories: Dict[str, Dict[str, str]] = {}
        self.subcategories: Dict[Tuple[str, str], Dict[str, str]] = {}
        self.transactions: Dict[str, Dict[str, str]] = {}
        self.original_transactions: Dict[str, Dict[str, str]] = {}
        self.transaction_spans: Dict[str, Any] = {}

        account_spans = document.spans_for("Account")
        currency_spans = document.spans_for("Currency")
        payment_spans = document.spans_for("Payment")
        party_spans = document.spans_for("Party")
        category_spans = document.spans_for("Category")
        subcategory_spans = document.spans_for("Sub_category")
        transaction_spans = document.spans_for("Transaction")
        for element, _span in zip(document.root.findall("Account"), account_spans):
            if element.get("Number"):
                self.accounts[element.get("Number")] = dict(element.attrib)
        for element, _span in zip(document.root.findall("Currency"), currency_spans):
            if element.get("Nb"):
                self.currencies[element.get("Nb")] = dict(element.attrib)
        for element, _span in zip(document.root.findall("Payment"), payment_spans):
            if element.get("Number"):
                self.payments[element.get("Number")] = dict(element.attrib)
        for element, _span in zip(document.root.findall("Party"), party_spans):
            if element.get("Nb"):
                self.parties[element.get("Nb")] = dict(element.attrib)
        for element, _span in zip(document.root.findall("Category"), category_spans):
            if element.get("Nb"):
                self.categories[element.get("Nb")] = dict(element.attrib)
        for element, _span in zip(document.root.findall("Sub_category"), subcategory_spans):
            key = (element.get("Nbc"), element.get("Nb"))
            if all(key):
                self.subcategories[(str(key[0]), str(key[1]))] = dict(element.attrib)
        for element, span in zip(document.root.findall("Transaction"), transaction_spans):
            transaction_id = element.get("Nb")
            if transaction_id:
                attributes = dict(element.attrib)
                self.transactions[transaction_id] = attributes
                self.original_transactions[transaction_id] = dict(attributes)
                self.transaction_spans[transaction_id] = span

        self.next_party = self._next_id(self.parties)
        self.next_category = self._next_id(self.categories)
        self.next_transaction = self._next_id(self.transactions)
        self.next_subcategories: Dict[str, int] = {}

        self.new_records: List[Tuple[str, Dict[str, str]]] = []
        self.new_transaction_ids: List[str] = []
        self.deleted_transactions: set[str] = set()
        self.structural_touched: set[str] = set()
        self.outcomes: List[Dict[str, Any]] = []

    @staticmethod
    def _next_id(records: Mapping[str, Any]) -> int:
        maximum = 0
        for key in records:
            try:
                maximum = max(maximum, int(key))
            except (ValueError, TypeError):
                continue
        return maximum + 1

    def _allocate_subcategory(self, category_id: str) -> str:
        if category_id not in self.next_subcategories:
            maximum = 0
            for parent, number in self.subcategories:
                if parent == category_id:
                    try:
                        maximum = max(maximum, int(number))
                    except ValueError:
                        pass
            self.next_subcategories[category_id] = maximum + 1
        value = self.next_subcategories[category_id]
        self.next_subcategories[category_id] += 1
        return str(value)

    def _outcome(
        self,
        client_index: int,
        operation: str,
        record_type: str,
        record_id: str,
        role: str = "primary",
        auto_created: bool = False,
        **extra: Any,
    ) -> None:
        result = {
            "operationIndex": client_index,
            "operation": operation,
            "recordType": record_type,
            "recordId": str(record_id),
            "role": role,
            "autoCreated": bool(auto_created),
        }
        result.update(extra)
        self.outcomes.append(result)

    def _single_name_match(
        self,
        records: Mapping[str, Mapping[str, str]],
        attribute: str,
        name: Any,
        record_type: str,
        predicate=None,
    ) -> Optional[str]:
        display = _clean_name(name, record_type)
        key = display.casefold()
        matches = [
            record_id
            for record_id, attributes in records.items()
            if _name_key(attributes.get(attribute, ""), record_type) == key
            and (predicate is None or predicate(attributes))
        ]
        if len(matches) > 1:
            raise MutationError(
                "%s name %r is ambiguous; matching IDs: %s"
                % (record_type, display, ", ".join(matches))
            )
        return matches[0] if matches else None

    def _resolve_party(
        self,
        raw: Mapping[str, Any],
        client_index: int,
        allow_create: bool,
    ) -> str:
        if "partyId" in raw and "partyName" in raw:
            raise MutationError("Use either partyId or partyName, not both")
        if "partyId" in raw:
            party_id = _canonical_id(raw["partyId"], "partyId", allow_zero=True)
            if party_id != "0" and party_id not in self.parties:
                raise MutationError("Unknown party %s" % party_id)
            return party_id
        if "partyName" not in raw or raw.get("partyName") in (None, ""):
            return "0"
        display = _clean_name(raw["partyName"], "Party")
        match = self._single_name_match(self.parties, "Na", display, "Party")
        if match:
            return match
        if not allow_create or not _bool(raw, "createMissing", False):
            raise MutationError("Party %r does not exist" % display)
        party_id = str(self.next_party)
        self.next_party += 1
        attributes = {
            "Nb": party_id,
            "Na": display,
            "Txt": "(null)",
            "Search": "(null)",
            "IgnCase": "0",
            "UseRegex": "0",
        }
        self.parties[party_id] = attributes
        self.new_records.append(("Party", attributes))
        self._outcome(client_index, "CreateParty", "Party", party_id, "party", True)
        return party_id

    def _resolve_category(
        self,
        raw: Mapping[str, Any],
        amount: Decimal,
        client_index: int,
        allow_create: bool,
    ) -> Tuple[str, str]:
        if "categoryId" in raw and "categoryName" in raw:
            raise MutationError("Use either categoryId or categoryName, not both")
        if "subcategoryId" in raw and "subcategoryName" in raw:
            raise MutationError("Use either subcategoryId or subcategoryName, not both")
        expected_kind = "1" if amount < 0 else "0" if amount > 0 else None
        requested_kind = raw.get("categoryKind")
        if requested_kind is not None:
            if not isinstance(requested_kind, int) or isinstance(requested_kind, bool) or requested_kind not in (0, 1):
                raise MutationError("categoryKind must be 0 (credit) or 1 (debit)")
            if expected_kind is not None and str(requested_kind) != expected_kind:
                raise MutationError("categoryKind does not match the transaction amount direction")
        desired_kind = expected_kind if expected_kind is not None else (str(requested_kind) if requested_kind is not None else None)

        if "categoryId" in raw:
            category_id = _canonical_id(raw.get("categoryId", "0"), "categoryId", allow_zero=True)
            if category_id != "0":
                category = self.categories.get(category_id)
                if category is None:
                    raise MutationError("Unknown category %s" % category_id)
                if category.get("Kd") == "2":
                    raise MutationError("Special categories are reserved for breakdown transactions")
                if desired_kind is not None and category.get("Kd") != desired_kind:
                    raise MutationError("Category does not match the transaction amount direction")
        elif "categoryName" in raw and raw.get("categoryName") not in (None, ""):
            display = _clean_name(raw["categoryName"], "Category")
            match = self._single_name_match(
                self.categories,
                "Na",
                display,
                "Category",
                predicate=lambda attrs: attrs.get("Kd") in ("0", "1")
                and (desired_kind is None or attrs.get("Kd") == desired_kind),
            )
            if match:
                category_id = match
            else:
                all_name_matches = self._single_name_match(
                    self.categories,
                    "Na",
                    display,
                    "Category",
                    predicate=lambda attrs: attrs.get("Kd") in ("0", "1", "2"),
                )
                if all_name_matches:
                    raise MutationError("Category %r exists but not with the required kind" % display)
                if not allow_create or not _bool(raw, "createMissing", False):
                    raise MutationError("Category %r does not exist" % display)
                if desired_kind is None:
                    raise MutationError("categoryKind is required for a zero amount")
                category_id = str(self.next_category)
                self.next_category += 1
                attributes = {"Nb": category_id, "Na": display, "Kd": desired_kind}
                self.categories[category_id] = attributes
                self.new_records.append(("Category", attributes))
                self._outcome(client_index, "CreateCategory", "Category", category_id, "category", True)
        else:
            if requested_kind is not None:
                raise MutationError("categoryKind requires categoryName or categoryId")
            category_id = "0"

        if category_id == "0":
            if raw.get("subcategoryId") not in NULLS or raw.get("subcategoryName") not in (None, ""):
                raise MutationError("A subcategory cannot be used without a category")
            return "0", "0"

        if "subcategoryId" in raw:
            subcategory_id = _canonical_id(raw.get("subcategoryId", "0"), "subcategoryId", allow_zero=True)
            if subcategory_id != "0" and (category_id, subcategory_id) not in self.subcategories:
                raise MutationError("Unknown subcategory %s/%s" % (category_id, subcategory_id))
            return category_id, subcategory_id
        if "subcategoryName" not in raw or raw.get("subcategoryName") in (None, ""):
            return category_id, "0"
        display = _clean_name(raw["subcategoryName"], "Subcategory")
        key = display.casefold()
        matches = [
            number
            for (parent, number), attrs in self.subcategories.items()
            if parent == category_id and _name_key(attrs.get("Na", ""), "Subcategory") == key
        ]
        if len(matches) > 1:
            raise MutationError("Subcategory %r is ambiguous in category %s" % (display, category_id))
        if matches:
            return category_id, matches[0]
        if not allow_create or not _bool(raw, "createMissing", False):
            raise MutationError("Subcategory %r does not exist in category %s" % (display, category_id))
        subcategory_id = self._allocate_subcategory(category_id)
        attributes = {"Nbc": category_id, "Nb": subcategory_id, "Na": display}
        self.subcategories[(category_id, subcategory_id)] = attributes
        self.new_records.append(("Sub_category", attributes))
        self._outcome(client_index, "CreateSubcategory", "Sub_category", subcategory_id, "subcategory", True, categoryId=category_id)
        return category_id, subcategory_id

    def _payment(
        self,
        account_id: str,
        payment_id: Any,
        amount: Decimal,
        field: str,
        strict: bool = True,
    ) -> str:
        payment_id = _canonical_id(payment_id, field, allow_zero=True)
        if payment_id == "0":
            return "0"
        payment = self.payments.get(payment_id)
        if payment is None:
            raise MutationError("Unknown payment method %s" % payment_id)
        if strict and payment.get("Account") != account_id:
            raise MutationError("Payment method %s does not belong to account %s" % (payment_id, account_id))
        expected = "1" if amount < 0 else "2" if amount > 0 else None
        if strict and expected and payment.get("Sign", "0") not in ("0", expected):
            raise MutationError("Payment method %s has the wrong debit/credit sign" % payment_id)
        return payment_id

    def _account_currency(self, account_id: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        account = self.accounts.get(account_id)
        if account is None:
            raise MutationError("Unknown account %s" % account_id)
        currency = self.currencies.get(account.get("Currency", ""))
        if currency is None:
            raise MutationError("Account %s references a missing currency" % account_id)
        return account, currency

    def _validate_normal(self, attrs: Dict[str, str], strict_payment: bool, enforce_kind: bool) -> None:
        account, currency = self._account_currency(attrs["Ac"])
        if attrs.get("Exb", "0") == "0" and attrs.get("Cu") != account.get("Currency"):
            raise MutationError("A normal transaction must use its account currency")
        attrs["Am"] = _amount_text(attrs["Am"], currency)
        amount = Decimal(attrs["Am"])
        party = attrs.get("Pa", "0")
        if party not in ("0", "(null)") and party not in self.parties:
            raise MutationError("Unknown party %s" % party)
        attrs["Pn"] = self._payment(attrs["Ac"], attrs.get("Pn", "0"), amount, "paymentMethodId", strict_payment)
        category_id = attrs.get("Ca", "0")
        subcategory_id = attrs.get("Sca", "0")
        if category_id in ("0", "(null)"):
            if subcategory_id not in ("0", "(null)"):
                raise MutationError("A subcategory cannot be used without a category")
        else:
            category = self.categories.get(category_id)
            if category is None:
                raise MutationError("Unknown category %s" % category_id)
            if subcategory_id not in ("0", "(null)") and (category_id, subcategory_id) not in self.subcategories:
                raise MutationError("Unknown subcategory %s/%s" % (category_id, subcategory_id))
            if enforce_kind:
                kind = category.get("Kd")
                if kind == "2":
                    raise MutationError("Special categories are reserved for breakdown transactions")
                if amount < 0 and kind != "1":
                    raise MutationError("A debit transaction requires a debit category")
                if amount > 0 and kind != "0":
                    raise MutationError("A credit transaction requires a credit category")
        if attrs.get("Ma", "0") not in ("0", "1", "2", "3"):
            raise MutationError("Marked state must be between 0 and 3")
        _date(attrs.get("Dt"), "date")
        if attrs.get("Dv") not in (None, "(null)"):
            _date(attrs.get("Dv"), "valueDate")

    def _touch(self, *transaction_ids: str) -> None:
        for transaction_id in transaction_ids:
            if transaction_id in self.structural_touched:
                raise MutationConflictError("Transaction %s is structurally mutated more than once in one batch" % transaction_id)
        self.structural_touched.update(transaction_ids)

    def _require_reconciled_confirmation(self, raw: Mapping[str, Any], records: Sequence[Mapping[str, str]]) -> None:
        ids = [record.get("Nb", "?") for record in records if _is_reconciled(record)]
        if ids and not _bool(raw, "allowReconciled", False):
            raise ConfirmationRequiredError(
                "reconciled-transaction",
                ids,
                "The operation affects reconciled transaction(s) %s; explicit confirmation is required" % ", ".join(ids),
            )

    def _new_transaction_id(self) -> str:
        value = str(self.next_transaction)
        self.next_transaction += 1
        return value

    def _base_transaction(
        self,
        raw: Mapping[str, Any],
        account_id: str,
        transaction_id: str,
        currency_id: str,
        amount_text: str,
        party_id: str,
        payment_id: str,
    ) -> Dict[str, str]:
        marked = raw.get("marked", 0)
        if not isinstance(marked, int) or isinstance(marked, bool) or marked not in (0, 1, 2, 3):
            raise MutationError("marked must be an integer between 0 and 3")
        return {
            "Ac": account_id,
            "Nb": transaction_id,
            "Id": _nullable(raw.get("importedId")),
            "Dt": _date(_required(raw, "date")),
            "Dv": _date(raw.get("valueDate"), "valueDate", allow_null=True),
            "Cu": currency_id,
            "Am": amount_text,
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
            "Ma": str(marked),
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

    def create_party(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("name", "text", "search", "ignoreCase", "useRegex"))
        name = _clean_name(_required(raw, "name"), "Party")
        party_id = str(self.next_party)
        self.next_party += 1
        attrs = {
            "Nb": party_id,
            "Na": name,
            "Txt": _nullable(raw.get("text")),
            "Search": _nullable(raw.get("search")),
            "IgnCase": "1" if _bool(raw, "ignoreCase", False) else "0",
            "UseRegex": "1" if _bool(raw, "useRegex", False) else "0",
        }
        self.parties[party_id] = attrs
        self.new_records.append(("Party", attrs))
        self._outcome(client_index, "CreateParty", "Party", party_id)

    def create_category(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("name", "kind"))
        kind = _required(raw, "kind")
        if not isinstance(kind, int) or isinstance(kind, bool) or kind not in (0, 1, 2):
            raise MutationError("kind must be 0, 1, or 2")
        category_id = str(self.next_category)
        self.next_category += 1
        attrs = {"Nb": category_id, "Na": _clean_name(_required(raw, "name"), "Category"), "Kd": str(kind)}
        self.categories[category_id] = attrs
        self.new_records.append(("Category", attrs))
        self._outcome(client_index, "CreateCategory", "Category", category_id)

    def create_subcategory(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("categoryId", "name"))
        category_id = _canonical_id(_required(raw, "categoryId"), "categoryId")
        if category_id not in self.categories:
            raise MutationError("Unknown category %s" % category_id)
        subcategory_id = self._allocate_subcategory(category_id)
        attrs = {"Nbc": category_id, "Nb": subcategory_id, "Na": _clean_name(_required(raw, "name"), "Subcategory")}
        self.subcategories[(category_id, subcategory_id)] = attrs
        self.new_records.append(("Sub_category", attrs))
        self._outcome(client_index, "CreateSubcategory", "Sub_category", subcategory_id, categoryId=category_id)

    def create_transaction(self, raw: Mapping[str, Any], client_index: int) -> None:
        allowed = (
            "accountId", "date", "amount", "paymentMethodId", "partyId", "partyName",
            "categoryId", "categoryName", "subcategoryId", "subcategoryName", "createMissing",
            "categoryKind", "note", "valueDate", "currencyId", "marked", "financialYear",
            "budgetId", "subbudgetId", "paymentReference", "voucher", "bankReference", "importedId",
        )
        _strict_fields(raw, allowed)
        account_id = _canonical_id(_required(raw, "accountId"), "accountId")
        account, currency = self._account_currency(account_id)
        currency_id = str(raw.get("currencyId") or account.get("Currency"))
        if currency_id != account.get("Currency"):
            raise MutationError("A normal transaction must use its account currency")
        amount = _decimal(_required(raw, "amount"))
        amount_text = _amount_text(amount, currency)
        party_id = self._resolve_party(raw, client_index, allow_create=True)
        category_id, subcategory_id = self._resolve_category(raw, amount, client_index, allow_create=True)
        payment_id = self._payment(account_id, raw.get("paymentMethodId", "0"), amount, "paymentMethodId", True)
        transaction_id = self._new_transaction_id()
        attrs = self._base_transaction(raw, account_id, transaction_id, currency_id, amount_text, party_id, payment_id)
        attrs["Ca"] = category_id
        attrs["Sca"] = subcategory_id
        self._validate_normal(attrs, strict_payment=True, enforce_kind=True)
        self.transactions[transaction_id] = attrs
        self.new_transaction_ids.append(transaction_id)
        self._outcome(client_index, "CreateTransaction", "Transaction", transaction_id, "transaction")

    def _existing_transaction(self, value: Any) -> Tuple[str, Dict[str, str]]:
        transaction_id = _canonical_id(value, "transactionId")
        transaction = self.transactions.get(transaction_id)
        if transaction is None or transaction_id in self.deleted_transactions:
            raise RecordNotFoundError("Transaction %s does not exist" % transaction_id)
        return transaction_id, transaction

    def update_transaction(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("transactionId", "changes"))
        transaction_id, existing = self._existing_transaction(_required(raw, "transactionId"))
        if any(existing.get(name, "0") not in ("0", "(null)") for name in ("Br", "Trt", "Mo")):
            raise MutationError("Transfer, breakdown and split-child transactions require their dedicated operation")
        self._touch(transaction_id)
        changes = _required(raw, "changes")
        if not isinstance(changes, Mapping) or not changes:
            raise MutationError("updateTransaction changes must be a non-empty JSON object")
        allowed = {
            "accountId", "date", "valueDate", "currencyId", "amount", "partyId", "categoryId",
            "subcategoryId", "note", "paymentMethodId", "paymentReference", "marked", "financialYear",
            "budgetId", "subbudgetId", "voucher", "bankReference",
        }
        unknown = sorted(set(changes) - allowed)
        if unknown:
            raise MutationError("updateTransaction contains unsupported changes: %s" % ", ".join(unknown))
        candidate = dict(existing)
        if "accountId" in changes:
            candidate["Ac"] = _canonical_id(changes["accountId"], "accountId")
            account, _currency = self._account_currency(candidate["Ac"])
            if "currencyId" not in changes:
                candidate["Cu"] = account.get("Currency", candidate["Cu"])
        if "currencyId" in changes:
            candidate["Cu"] = _canonical_id(changes["currencyId"], "currencyId")
        if "date" in changes: candidate["Dt"] = _date(changes["date"])
        if "valueDate" in changes: candidate["Dv"] = _date(changes["valueDate"], "valueDate", True)
        if "amount" in changes: candidate["Am"] = str(changes["amount"])
        if "partyId" in changes: candidate["Pa"] = _canonical_id(changes["partyId"], "partyId", True)
        if "categoryId" in changes:
            candidate["Ca"] = _canonical_id(changes["categoryId"], "categoryId", True)
            if "subcategoryId" not in changes: candidate["Sca"] = "0"
        if "subcategoryId" in changes: candidate["Sca"] = _canonical_id(changes["subcategoryId"], "subcategoryId", True)
        if candidate["Ca"] == "0": candidate["Sca"] = "0"
        for field, attribute in (("note", "No"), ("paymentReference", "Pc"), ("voucher", "Vo"), ("bankReference", "Ba")):
            if field in changes: candidate[attribute] = _nullable(changes[field])
        if "paymentMethodId" in changes: candidate["Pn"] = _canonical_id(changes["paymentMethodId"], "paymentMethodId", True)
        if "marked" in changes:
            marked = changes["marked"]
            if not isinstance(marked, int) or isinstance(marked, bool) or marked not in (0, 1, 2, 3):
                raise MutationError("marked must be between 0 and 3")
            candidate["Ma"] = str(marked)
        for field, attribute in (("financialYear", "Fi"), ("budgetId", "Bu"), ("subbudgetId", "Sbu")):
            if field in changes: candidate[attribute] = str(changes[field])
        strict_payment = bool({"accountId", "currencyId", "amount", "paymentMethodId"} & set(changes))
        enforce_kind = bool({"amount", "categoryId", "subcategoryId"} & set(changes))
        self._validate_normal(candidate, strict_payment, enforce_kind)
        self.transactions[transaction_id] = candidate
        self._outcome(client_index, "UpdateTransaction", "Transaction", transaction_id)

    def delete_transaction(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("transactionId",))
        transaction_id, existing = self._existing_transaction(_required(raw, "transactionId"))
        if any(existing.get(name, "0") not in ("0", "(null)") for name in ("Br", "Trt", "Mo")):
            raise MutationError("Transfer, breakdown and split-child transactions require their dedicated operation")
        self._touch(transaction_id)
        for other_id, other in self.transactions.items():
            if other_id != transaction_id and other_id not in self.deleted_transactions and (
                other.get("Trt") == transaction_id or other.get("Mo") == transaction_id
            ):
                raise MutationError("Transaction %s is referenced by transaction %s" % (transaction_id, other_id))
        self.deleted_transactions.add(transaction_id)
        self._outcome(client_index, "DeleteTransaction", "Transaction", transaction_id)

    def _transfer_pair(self, value: Any) -> Tuple[str, Dict[str, str], str, Dict[str, str]]:
        source_id, source = self._existing_transaction(value)
        if source.get("Br", "0") not in ("0", "(null)") or source.get("Mo", "0") not in ("0", "(null)"):
            raise MutationError("Breakdown or split-child transaction requires its dedicated editor")
        counterpart_id = source.get("Trt", "0")
        counterpart = self.transactions.get(counterpart_id)
        if counterpart_id in ("0", "(null)") or counterpart is None or counterpart_id in self.deleted_transactions or counterpart.get("Trt", "0") != source_id:
            raise MutationError("Transaction is not a valid reciprocal transfer")
        if source.get("Cu") != counterpart.get("Cu"):
            raise MutationError("Cross-currency transfers are not yet safely editable")
        return source_id, source, counterpart_id, counterpart

    def create_transfer(self, raw: Mapping[str, Any], client_index: int) -> None:
        allowed = (
            "accountId", "targetAccountId", "date", "amount", "paymentMethodId", "targetPaymentMethodId",
            "targetPaymentReference", "partyId", "partyName", "createMissing", "note", "valueDate", "marked",
            "financialYear", "budgetId", "subbudgetId", "paymentReference", "voucher", "bankReference",
        )
        _strict_fields(raw, allowed)
        source_account_id = _canonical_id(_required(raw, "accountId"), "accountId")
        target_account_id = _canonical_id(_required(raw, "targetAccountId"), "targetAccountId")
        if source_account_id == target_account_id:
            raise MutationError("Transfer destination must be a different account")
        source_account, currency = self._account_currency(source_account_id)
        target_account, target_currency = self._account_currency(target_account_id)
        if source_account.get("Currency") != target_account.get("Currency"):
            raise MutationError("Cross-currency transfers are not yet safely editable")
        amount = _decimal(_required(raw, "amount"))
        if amount == 0: raise MutationError("Transfer amount cannot be zero")
        party_id = self._resolve_party(raw, client_index, allow_create=True)
        source_payment = self._payment(source_account_id, raw.get("paymentMethodId", "0"), amount, "paymentMethodId", True)
        target_payment = self._payment(target_account_id, raw.get("targetPaymentMethodId", "0"), -amount, "targetPaymentMethodId", True)
        source_id = self._new_transaction_id()
        counterpart_id = self._new_transaction_id()
        source = self._base_transaction(raw, source_account_id, source_id, source_account.get("Currency"), _amount_text(amount, currency), party_id, source_payment)
        source["Trt"] = counterpart_id
        counterpart = dict(source)
        counterpart.update({
            "Ac": target_account_id,
            "Nb": counterpart_id,
            "Cu": target_account.get("Currency"),
            "Am": _amount_text(-amount, target_currency),
            "Pn": target_payment,
            "Pc": _nullable(raw.get("targetPaymentReference")),
            "Ma": "0",
            "Re": "0",
            "Trt": source_id,
        })
        self.transactions[source_id] = source
        self.transactions[counterpart_id] = counterpart
        self.new_transaction_ids.extend((source_id, counterpart_id))
        self._outcome(client_index, "CreateTransfer", "Transaction", source_id, "source")
        self._outcome(client_index, "CreateTransfer", "Transaction", counterpart_id, "counterpart")

    def update_transfer(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("transactionId", "changes", "allowReconciled"))
        source_id, source, counterpart_id, counterpart = self._transfer_pair(_required(raw, "transactionId"))
        self._touch(source_id, counterpart_id)
        self._require_reconciled_confirmation(raw, (source, counterpart))
        changes = _required(raw, "changes")
        if not isinstance(changes, Mapping) or not changes:
            raise MutationError("updateTransfer changes must be a non-empty JSON object")
        allowed = {
            "date", "valueDate", "amount", "partyId", "note", "paymentMethodId", "paymentReference",
            "marked", "voucher", "bankReference", "targetAccountId", "targetPaymentMethodId", "targetPaymentReference",
        }
        unknown = sorted(set(changes) - allowed)
        if unknown: raise MutationError("updateTransfer contains unsupported changes: %s" % ", ".join(unknown))
        source_attrs = dict(source)
        counterpart_attrs = dict(counterpart)
        target_account_id = _canonical_id(changes.get("targetAccountId", counterpart_attrs["Ac"]), "targetAccountId")
        if target_account_id == source_attrs["Ac"]: raise MutationError("Transfer destination must be different")
        target_account, target_currency = self._account_currency(target_account_id)
        source_account, source_currency = self._account_currency(source_attrs["Ac"])
        if target_account.get("Currency") != source_account.get("Currency"):
            raise MutationError("Cross-currency transfers are not yet safely editable")
        if "date" in changes: source_attrs["Dt"] = _date(changes["date"])
        if "valueDate" in changes: source_attrs["Dv"] = _date(changes["valueDate"], "valueDate", True)
        if "amount" in changes: source_attrs["Am"] = _amount_text(changes["amount"], source_currency)
        amount = Decimal(source_attrs["Am"])
        if amount == 0: raise MutationError("Transfer amount cannot be zero")
        if "partyId" in changes:
            party_id = _canonical_id(changes["partyId"], "partyId", True)
            if party_id != "0" and party_id not in self.parties: raise MutationError("Unknown party %s" % party_id)
            source_attrs["Pa"] = party_id
        for field, attribute in (("note", "No"), ("paymentReference", "Pc"), ("voucher", "Vo"), ("bankReference", "Ba")):
            if field in changes: source_attrs[attribute] = _nullable(changes[field])
        if "marked" in changes:
            marked = changes["marked"]
            if not isinstance(marked, int) or isinstance(marked, bool) or marked not in (0, 1, 2, 3): raise MutationError("marked must be between 0 and 3")
            source_attrs["Ma"] = str(marked)
        if "paymentMethodId" in changes: source_attrs["Pn"] = str(changes["paymentMethodId"])
        source_attrs["Pn"] = self._payment(source_attrs["Ac"], source_attrs.get("Pn", "0"), amount, "paymentMethodId", bool({"amount", "paymentMethodId"} & set(changes)))

        target_changed = target_account_id != counterpart_attrs["Ac"]
        if target_changed:
            new_counterpart_id = self._new_transaction_id()
            source_attrs["Trt"] = new_counterpart_id
            target_payment = self._payment(target_account_id, changes.get("targetPaymentMethodId", "0"), -amount, "targetPaymentMethodId", True)
            new_counterpart = dict(source_attrs)
            new_counterpart.update({
                "Ac": target_account_id,
                "Nb": new_counterpart_id,
                "Am": _amount_text(-amount, target_currency),
                "Pn": target_payment,
                "Pc": _nullable(changes.get("targetPaymentReference")),
                # Grisbi preserves the old counterpart's bank-check state and value date
                # when the destination is changed.
                "Dv": counterpart_attrs.get("Dv", "(null)"),
                "Ma": counterpart_attrs.get("Ma", "0"),
                "Re": counterpart_attrs.get("Re", "0"),
                "Trt": source_id,
            })
            self.transactions[source_id] = source_attrs
            self.deleted_transactions.add(counterpart_id)
            self.transactions[new_counterpart_id] = new_counterpart
            self.new_transaction_ids.append(new_counterpart_id)
            self._outcome(client_index, "UpdateTransfer", "Transaction", source_id, "source")
            self._outcome(client_index, "UpdateTransfer", "Transaction", new_counterpart_id, "counterpart", replacedTransactionId=counterpart_id)
            return

        for attribute in ("Dt", "Pa", "No", "Vo", "Ba", "Exb", "Exr", "Exf", "Fi", "Bu", "Sbu"):
            counterpart_attrs[attribute] = source_attrs[attribute]
        counterpart_attrs["Ca"] = "0"
        counterpart_attrs["Sca"] = "0"
        counterpart_attrs["Br"] = "0"
        counterpart_attrs["Mo"] = "0"
        counterpart_attrs["Am"] = _amount_text(-amount, target_currency)
        if "targetPaymentMethodId" in changes: counterpart_attrs["Pn"] = str(changes["targetPaymentMethodId"])
        counterpart_attrs["Pn"] = self._payment(target_account_id, counterpart_attrs.get("Pn", "0"), -amount, "targetPaymentMethodId", bool({"amount", "targetPaymentMethodId"} & set(changes)))
        if "targetPaymentReference" in changes: counterpart_attrs["Pc"] = _nullable(changes["targetPaymentReference"])
        self.transactions[source_id] = source_attrs
        self.transactions[counterpart_id] = counterpart_attrs
        self._outcome(client_index, "UpdateTransfer", "Transaction", source_id, "source")
        self._outcome(client_index, "UpdateTransfer", "Transaction", counterpart_id, "counterpart")

    def delete_transfer(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("transactionId", "allowReconciled"))
        source_id, source, counterpart_id, counterpart = self._transfer_pair(_required(raw, "transactionId"))
        self._touch(source_id, counterpart_id)
        self._require_reconciled_confirmation(raw, (source, counterpart))
        self.deleted_transactions.update((source_id, counterpart_id))
        self._outcome(client_index, "DeleteTransfer", "Transaction", source_id, "source")
        self._outcome(client_index, "DeleteTransfer", "Transaction", counterpart_id, "counterpart")

    def convert_transaction_to_transfer(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("transactionId", "targetAccountId", "paymentMethodId", "targetPaymentMethodId", "targetPaymentReference", "allowReconciled"))
        transaction_id, source = self._existing_transaction(_required(raw, "transactionId"))
        if any(source.get(name, "0") not in ("0", "(null)") for name in ("Br", "Trt", "Mo")):
            raise MutationError("Only a normal transaction can be converted to a transfer")
        self._touch(transaction_id)
        self._require_reconciled_confirmation(raw, (source,))
        target_account_id = _canonical_id(_required(raw, "targetAccountId"), "targetAccountId")
        if target_account_id == source["Ac"]: raise MutationError("Transfer destination must be different")
        source_account, currency = self._account_currency(source["Ac"])
        target_account, target_currency = self._account_currency(target_account_id)
        if source_account.get("Currency") != target_account.get("Currency"):
            raise MutationError("Cross-currency transfers are not yet safely editable")
        amount = Decimal(source["Am"])
        if amount == 0: raise MutationError("Transfer amount cannot be zero")
        source_attrs = dict(source)
        if "paymentMethodId" in raw: source_attrs["Pn"] = str(raw["paymentMethodId"])
        source_attrs["Pn"] = self._payment(source_attrs["Ac"], source_attrs.get("Pn", "0"), amount, "paymentMethodId", True)
        counterpart_id = self._new_transaction_id()
        target_payment = self._payment(target_account_id, raw.get("targetPaymentMethodId", "0"), -amount, "targetPaymentMethodId", True)
        source_attrs.update({"Ca": "0", "Sca": "0", "Trt": counterpart_id})
        counterpart = dict(source_attrs)
        counterpart.update({
            "Ac": target_account_id,
            "Nb": counterpart_id,
            "Am": _amount_text(-amount, target_currency),
            "Pn": target_payment,
            "Pc": _nullable(raw.get("targetPaymentReference")),
            "Ma": "0",
            "Re": "0",
            "Trt": transaction_id,
        })
        self.transactions[transaction_id] = source_attrs
        self.transactions[counterpart_id] = counterpart
        self.new_transaction_ids.append(counterpart_id)
        self._outcome(client_index, "ConvertTransactionToTransfer", "Transaction", transaction_id, "source")
        self._outcome(client_index, "ConvertTransactionToTransfer", "Transaction", counterpart_id, "counterpart")

    def convert_transfer_to_transaction(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("transactionId", "categoryId", "subcategoryId", "allowReconciled"))
        source_id, source, counterpart_id, counterpart = self._transfer_pair(_required(raw, "transactionId"))
        self._touch(source_id, counterpart_id)
        self._require_reconciled_confirmation(raw, (source, counterpart))
        category_id = _canonical_id(_required(raw, "categoryId"), "categoryId", True)
        subcategory_id = _canonical_id(raw.get("subcategoryId", "0"), "subcategoryId", True)
        source_attrs = dict(source)
        source_attrs.update({"Ca": category_id, "Sca": subcategory_id if category_id != "0" else "0", "Trt": "0"})
        self._validate_normal(source_attrs, strict_payment=False, enforce_kind=True)
        self.transactions[source_id] = source_attrs
        self.deleted_transactions.add(counterpart_id)
        self._outcome(client_index, "ConvertTransferToTransaction", "Transaction", source_id, "transaction")
        self._outcome(client_index, "DeleteTransferCounterpart", "Transaction", counterpart_id, "counterpart")

    def set_transaction_marks(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("marks",))
        marks = _required(raw, "marks")
        if not isinstance(marks, list) or not marks:
            raise MutationError("setTransactionMarks marks must be a non-empty array")
        if len(marks) > 1000:
            raise MutationError("setTransactionMarks exceeds the 1000-row limit")
        seen = set()
        changed = 0
        for item in marks:
            if not isinstance(item, list) or len(item) != 2:
                raise MutationError("Each mark entry must be [transactionId, 0|1]")
            transaction_id = _canonical_id(item[0], "transactionId")
            if transaction_id in seen:
                raise MutationConflictError("Transaction %s appears more than once in setTransactionMarks" % transaction_id)
            seen.add(transaction_id)
            marked = item[1]
            if not isinstance(marked, int) or isinstance(marked, bool) or marked not in (0, 1):
                raise MutationError("Quick mark state must be 0 or 1")
            _transaction_id, attrs = self._existing_transaction(transaction_id)
            current = attrs.get("Ma", "0")
            if current not in ("0", "1"):
                raise MarkStateError(
                    "Transaction %s is telepointed or reconciled and cannot be changed by quick marking" % transaction_id
                )
            if current != str(marked):
                attrs["Ma"] = str(marked)
                changed += 1
        self._outcome(client_index, "SetTransactionMarks", "Transaction", "*", "mark-batch", count=len(marks), changedCount=changed)

    def apply(self, raw: Mapping[str, Any], client_index: int) -> None:
        if not isinstance(raw, Mapping):
            raise MutationError("Every mutation operation must be a JSON object")
        operation_type = raw.get("type")
        if not isinstance(operation_type, str):
            raise MutationError("Mutation operation type must be text")
        dispatch = {
            "createParty": self.create_party,
            "createCategory": self.create_category,
            "createSubcategory": self.create_subcategory,
            "createTransaction": self.create_transaction,
            "updateTransaction": self.update_transaction,
            "deleteTransaction": self.delete_transaction,
            "createTransfer": self.create_transfer,
            "updateTransfer": self.update_transfer,
            "deleteTransfer": self.delete_transfer,
            "convertTransactionToTransfer": self.convert_transaction_to_transfer,
            "convertTransferToTransaction": self.convert_transfer_to_transaction,
            "setTransactionMarks": self.set_transaction_marks,
        }
        handler = dispatch.get(operation_type)
        if handler is None:
            raise MutationError("Unsupported mutation operation type: %s" % operation_type)
        handler(raw, client_index)

    def render(self, password: Optional[str] = None) -> Tuple[bytes, int, Any]:
        writer = LosslessPatchWriter(self.document)
        changed_records = 0
        for transaction_id, original in self.original_transactions.items():
            span = self.transaction_spans[transaction_id]
            if transaction_id in self.deleted_transactions:
                writer.delete(span)
                changed_records += 1
                continue
            current = self.transactions[transaction_id]
            if current == original:
                continue
            changed_keys = {
                key
                for key in set(original) | set(current)
                if original.get(key) != current.get(key)
            }
            if changed_keys == {"Ma"}:
                writer.replace_attribute(span, "Ma", current["Ma"])
            else:
                writer.replace_record(span, current)
            changed_records += 1
        for tag, attrs in self.new_records:
            writer.insert_record(tag, attrs)
            changed_records += 1
        for transaction_id in self.new_transaction_ids:
            if transaction_id not in self.deleted_transactions:
                writer.insert_record("Transaction", self.transactions[transaction_id])
                changed_records += 1
        if not writer.changed:
            return self.document.raw_bytes, changed_records, self.document
        xml_bytes = writer.render_xml()
        # Parse the final plain XML once for semantic verification. This avoids
        # decrypting/decompressing the just-produced output a second time.
        final_document = parse_document(xml_bytes)
        assert_valid_document(final_document)
        raw_bytes = encode_envelope(
            xml_bytes,
            self.document.envelope,
            password=password,
        )
        return raw_bytes, changed_records, final_document


def apply_phase6_operations(
    raw_bytes: bytes,
    raw_operations: Iterable[Mapping[str, Any]],
    password: Optional[str] = None,
) -> Phase6Result:
    operations = tuple(raw_operations)
    if not operations:
        raise MutationError("operations cannot be empty")
    if len(operations) > 1000:
        raise MutationError("Mutation batch exceeds the operation limit")
    document = parse_document(raw_bytes, password=password)
    session = Phase6Session(document)
    for client_index, raw in enumerate(operations):
        session.apply(raw, client_index)
    output, changed_records, final_document = session.render(password=password)
    warnings = tuple(
        {
            "code": issue.code,
            "message": issue.message,
            "tag": issue.tag,
            "recordId": issue.record_id,
            "severity": issue.severity,
        }
        for issue in warning_issues(final_document)
    )
    return Phase6Result(output, tuple(session.outcomes), warnings, changed_records)
