from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from .errors import MutationConflictError, MutationError, RecordNotFoundError
from .index import GsbIndex
from .model import GsbDocument
from .parser import parse_document
from .validator import assert_valid_document
from .writer import LosslessPatchWriter

Amount = Union[str, int, float, Decimal]
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


@dataclass(frozen=True)
class CreateParty:
    name: str
    text: Optional[str] = None
    search: Optional[str] = None
    ignore_case: bool = False
    use_regex: bool = False


@dataclass(frozen=True)
class CreateCategory:
    name: str
    kind: int


@dataclass(frozen=True)
class CreateSubcategory:
    category_id: str
    name: str


@dataclass(frozen=True)
class CreateTransaction:
    account_id: str
    date: str
    amount: Amount
    payment_method_id: str = "0"
    party_id: str = "0"
    category_id: str = "0"
    subcategory_id: str = "0"
    note: Optional[str] = None
    value_date: Optional[str] = None
    currency_id: Optional[str] = None
    marked: int = 0
    financial_year: str = "0"
    budget_id: str = "0"
    subbudget_id: str = "0"
    payment_reference: Optional[str] = None
    voucher: Optional[str] = None
    bank_reference: Optional[str] = None
    imported_id: Optional[str] = None


@dataclass(frozen=True)
class UpdateTransaction:
    transaction_id: str
    changes: Mapping[str, Any]


@dataclass(frozen=True)
class DeleteTransaction:
    transaction_id: str


MutationOperation = Union[
    CreateParty,
    CreateCategory,
    CreateSubcategory,
    CreateTransaction,
    UpdateTransaction,
    DeleteTransaction,
]


@dataclass(frozen=True)
class MutationOutcome:
    operation_index: int
    operation: str
    record_type: str
    record_id: str


@dataclass(frozen=True)
class MutationResult:
    raw_bytes: bytes
    xml_bytes: bytes
    outcomes: Tuple[MutationOutcome, ...]


_UPDATE_FIELDS = {
    "account_id": "Ac",
    "date": "Dt",
    "value_date": "Dv",
    "currency_id": "Cu",
    "amount": "Am",
    "party_id": "Pa",
    "category_id": "Ca",
    "subcategory_id": "Sca",
    "note": "No",
    "payment_method_id": "Pn",
    "payment_reference": "Pc",
    "marked": "Ma",
    "financial_year": "Fi",
    "budget_id": "Bu",
    "subbudget_id": "Sbu",
    "voucher": "Vo",
    "bank_reference": "Ba",
}


class _MutationSession:
    def __init__(self, document: GsbDocument):
        self.document = document
        self.index = GsbIndex.build(document)
        self.writer = LosslessPatchWriter(document)
        self.accounts = {
            key: record.attributes for key, record in self.index.accounts.items()
        }
        self.currencies = {
            key: record.attributes for key, record in self.index.currencies.items()
        }
        self.payments = {
            key: record.attributes for key, record in self.index.payments.items()
        }
        self.transactions = {
            key: record.attributes for key, record in self.index.transactions.items()
        }
        self.parties = {
            key: record.attributes for key, record in self.index.parties.items()
        }
        self.categories = {
            key: record.attributes for key, record in self.index.categories.items()
        }
        self.subcategories = {
            key: record.attributes for key, record in self.index.subcategories.items()
        }
        self.next_transaction = int(self.index.next_transaction_id())
        self.next_party = int(self.index.next_party_id())
        self.next_category = int(self.index.next_category_id())
        self.next_subcategories: Dict[str, int] = {}
        self.touched_transactions = set()

    @staticmethod
    def _required_name(value: str, record_type: str) -> str:
        if not isinstance(value, str):
            raise MutationError("%s name must be text" % record_type)
        name = value.strip()
        if not name:
            raise MutationError("%s name cannot be empty" % record_type)
        if any(ord(char) < 32 and char not in "\t\n\r" for char in name):
            raise MutationError(
                "%s name contains an unsupported control character" % record_type
            )
        return name

    @staticmethod
    def _id(value: Any, field: str, allow_zero: bool = True) -> str:
        text = str(value)
        try:
            number = int(text)
        except (TypeError, ValueError):
            raise MutationError("%s must be a numeric Grisbi identifier" % field)
        if number < 0 or (number == 0 and not allow_zero) or str(number) != text:
            raise MutationError("%s is not a canonical Grisbi identifier" % field)
        return text

    @staticmethod
    def _date(
        value: Optional[str],
        field: str,
        allow_null: bool = False,
    ) -> str:
        if value is None and allow_null:
            return "(null)"
        if not isinstance(value, str) or not _DATE_RE.match(value):
            raise MutationError("%s must use MM/DD/YYYY" % field)
        try:
            datetime.strptime(value, "%m/%d/%Y")
        except ValueError:
            raise MutationError("%s is not a valid calendar date" % field)
        return value

    def _currency_precision(self, currency_id: str) -> int:
        currency = self.currencies.get(currency_id)
        if currency is None:
            raise MutationError("Unknown currency %s" % currency_id)
        try:
            precision = int(currency.get("Fl", "2"))
        except ValueError:
            raise MutationError("Currency %s has invalid precision" % currency_id)
        if precision < 0 or precision > 12:
            raise MutationError("Currency %s has unsupported precision" % currency_id)
        return precision

    def _amount(self, value: Amount, currency_id: str) -> str:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise MutationError("Amount is not a valid decimal number")
        if not amount.is_finite():
            raise MutationError("Amount must be finite")
        precision = self._currency_precision(currency_id)
        quantum = Decimal(1).scaleb(-precision)
        try:
            quantized = amount.quantize(quantum)
        except InvalidOperation:
            raise MutationError(
                "Amount cannot be represented in currency %s" % currency_id
            )
        if quantized != amount:
            raise MutationError(
                "Amount has more than %d decimal places for currency %s"
                % (precision, currency_id)
            )
        return format(quantized, ".%df" % precision)

    @staticmethod
    def _nullable(value: Any) -> str:
        return "(null)" if value is None else str(value)

    @staticmethod
    def _protected_transaction(attributes: Mapping[str, str]) -> bool:
        return any(
            attributes.get(name, "0") not in ("0", "(null)")
            for name in ("Br", "Trt", "Mo")
        )

    def _validate_transaction(
        self,
        attributes: Mapping[str, str],
        enforce_category_kind: bool,
    ) -> None:
        account_id = attributes["Ac"]
        currency_id = attributes["Cu"]
        party_id = attributes["Pa"]
        category_id = attributes["Ca"]
        subcategory_id = attributes["Sca"]
        payment_id = attributes["Pn"]

        account = self.accounts.get(account_id)
        if account is None:
            raise MutationError("Unknown account %s" % account_id)
        if currency_id not in self.currencies:
            raise MutationError("Unknown currency %s" % currency_id)
        if (
            attributes.get("Exb", "0") == "0"
            and currency_id != account.get("Currency")
        ):
            raise MutationError("A normal transaction must use its account currency")
        if party_id not in ("0", "(null)") and party_id not in self.parties:
            raise MutationError("Unknown party %s" % party_id)
        if payment_id not in ("0", "(null)") and (
            account_id,
            payment_id,
        ) not in self.payments:
            raise MutationError(
                "Payment method %s does not belong to account %s"
                % (payment_id, account_id)
            )

        if category_id in ("0", "(null)"):
            if subcategory_id not in ("0", "(null)"):
                raise MutationError(
                    "A subcategory cannot be used without a category"
                )
        else:
            category = self.categories.get(category_id)
            if category is None:
                raise MutationError("Unknown category %s" % category_id)
            if subcategory_id not in ("0", "(null)") and (
                category_id,
                subcategory_id,
            ) not in self.subcategories:
                raise MutationError(
                    "Unknown subcategory %s/%s"
                    % (category_id, subcategory_id)
                )
            if enforce_category_kind:
                amount = Decimal(attributes["Am"])
                kind = category.get("Kd")
                if amount < 0 and kind != "1":
                    raise MutationError(
                        "A debit transaction requires a debit category"
                    )
                if amount > 0 and kind != "0":
                    raise MutationError(
                        "A credit transaction requires a credit category"
                    )
                if kind == "2":
                    raise MutationError(
                        "Special categories are reserved for transfer/split phases"
                    )

        marked = attributes.get("Ma", "0")
        if marked not in ("0", "1", "2", "3"):
            raise MutationError("Marked state must be between 0 and 3")
        self._date(attributes["Dt"], "date")
        if attributes.get("Dv") not in (None, "(null)"):
            self._date(attributes["Dv"], "value_date")
        if self._protected_transaction(attributes):
            raise MutationError(
                "Transfer and split transactions require their dedicated mutation phase"
            )

    def _allocate_subcategory(self, category_id: str) -> str:
        if category_id not in self.next_subcategories:
            self.next_subcategories[category_id] = int(
                self.index.next_subcategory_id(category_id)
            )
        allocated = self.next_subcategories[category_id]
        self.next_subcategories[category_id] += 1
        return str(allocated)

    def create_party(self, operation: CreateParty) -> str:
        record_id = str(self.next_party)
        self.next_party += 1
        attributes = {
            "Nb": record_id,
            "Na": self._required_name(operation.name, "Party"),
            "Txt": self._nullable(operation.text),
            "Search": self._nullable(operation.search),
            "IgnCase": "1" if operation.ignore_case else "0",
            "UseRegex": "1" if operation.use_regex else "0",
        }
        self.writer.insert_record("Party", attributes)
        self.parties[record_id] = attributes
        return record_id

    def create_category(self, operation: CreateCategory) -> str:
        if operation.kind not in (0, 1, 2):
            raise MutationError(
                "Category kind must be 0 (credit), 1 (debit), or 2 (special)"
            )
        record_id = str(self.next_category)
        self.next_category += 1
        attributes = {
            "Nb": record_id,
            "Na": self._required_name(operation.name, "Category"),
            "Kd": str(operation.kind),
        }
        self.writer.insert_record("Category", attributes)
        self.categories[record_id] = attributes
        return record_id

    def create_subcategory(self, operation: CreateSubcategory) -> str:
        category_id = self._id(
            operation.category_id,
            "category_id",
            allow_zero=False,
        )
        if category_id not in self.categories:
            raise MutationError("Unknown category %s" % category_id)
        record_id = self._allocate_subcategory(category_id)
        attributes = {
            "Nbc": category_id,
            "Nb": record_id,
            "Na": self._required_name(operation.name, "Subcategory"),
        }
        anchor = self.index.last_subcategory_span(category_id)
        self.writer.insert_record("Sub_category", attributes, after=anchor)
        self.subcategories[(category_id, record_id)] = attributes
        return record_id

    def create_transaction(self, operation: CreateTransaction) -> str:
        account_id = self._id(
            operation.account_id,
            "account_id",
            allow_zero=False,
        )
        account = self.accounts.get(account_id)
        if account is None:
            raise MutationError("Unknown account %s" % account_id)
        currency_id = self._id(
            operation.currency_id or account.get("Currency"),
            "currency_id",
            allow_zero=False,
        )
        record_id = str(self.next_transaction)
        self.next_transaction += 1
        category_id = self._id(operation.category_id, "category_id")
        subcategory_id = self._id(
            operation.subcategory_id,
            "subcategory_id",
        )
        if category_id == "0":
            subcategory_id = "0"
        attributes = {
            "Ac": account_id,
            "Nb": record_id,
            "Id": self._nullable(operation.imported_id),
            "Dt": self._date(operation.date, "date"),
            "Dv": self._date(
                operation.value_date,
                "value_date",
                allow_null=True,
            ),
            "Cu": currency_id,
            "Am": self._amount(operation.amount, currency_id),
            "Exb": "0",
            "Exr": "0.00",
            "Exf": "0.00",
            "Pa": self._id(operation.party_id, "party_id"),
            "Ca": category_id,
            "Sca": subcategory_id,
            "Br": "0",
            "No": self._nullable(operation.note),
            "Pn": self._id(
                operation.payment_method_id,
                "payment_method_id",
            ),
            "Pc": self._nullable(operation.payment_reference),
            "Ma": str(operation.marked),
            "Ar": "0",
            "Au": "0",
            "Re": "0",
            "Fi": str(operation.financial_year),
            "Bu": str(operation.budget_id),
            "Sbu": str(operation.subbudget_id),
            "Vo": self._nullable(operation.voucher),
            "Ba": self._nullable(operation.bank_reference),
            "Trt": "0",
            "Mo": "0",
        }
        self._validate_transaction(attributes, enforce_category_kind=True)
        self.writer.insert_record("Transaction", attributes)
        self.transactions[record_id] = attributes
        return record_id

    def update_transaction(self, operation: UpdateTransaction) -> str:
        transaction_id = self._id(
            operation.transaction_id,
            "transaction_id",
            allow_zero=False,
        )
        existing = self.transactions.get(transaction_id)
        record = self.index.transactions.get(transaction_id)
        if existing is None or record is None:
            raise RecordNotFoundError(
                "Transaction %s does not exist" % transaction_id
            )
        if transaction_id in self.touched_transactions:
            raise MutationConflictError(
                "Transaction %s is mutated more than once in one batch"
                % transaction_id
            )
        if self._protected_transaction(existing):
            raise MutationError(
                "Transfer and split transactions require their dedicated mutation phase"
            )
        if not isinstance(operation.changes, Mapping) or not operation.changes:
            raise MutationError(
                "Transaction update must contain at least one changed field"
            )
        unknown = sorted(set(operation.changes) - set(_UPDATE_FIELDS))
        if unknown:
            raise MutationError(
                "Unsupported transaction update fields: %s"
                % ", ".join(unknown)
            )

        candidate = dict(existing)
        changes = dict(operation.changes)
        if "account_id" in changes:
            account_id = self._id(
                changes["account_id"],
                "account_id",
                allow_zero=False,
            )
            account = self.accounts.get(account_id)
            if account is None:
                raise MutationError("Unknown account %s" % account_id)
            candidate["Ac"] = account_id
            if "currency_id" not in changes:
                candidate["Cu"] = account.get("Currency", candidate["Cu"])
        if "currency_id" in changes:
            candidate["Cu"] = self._id(
                changes["currency_id"],
                "currency_id",
                allow_zero=False,
            )
        if "date" in changes:
            candidate["Dt"] = self._date(changes["date"], "date")
        if "value_date" in changes:
            candidate["Dv"] = self._date(
                changes["value_date"],
                "value_date",
                allow_null=True,
            )
        if "amount" in changes:
            candidate["Am"] = self._amount(
                changes["amount"],
                candidate["Cu"],
            )
        if "party_id" in changes:
            candidate["Pa"] = self._id(changes["party_id"], "party_id")
        if "category_id" in changes:
            candidate["Ca"] = self._id(
                changes["category_id"],
                "category_id",
            )
            if "subcategory_id" not in changes:
                candidate["Sca"] = "0"
        if "subcategory_id" in changes:
            candidate["Sca"] = self._id(
                changes["subcategory_id"],
                "subcategory_id",
            )
        if candidate["Ca"] == "0":
            candidate["Sca"] = "0"
        if "note" in changes:
            candidate["No"] = self._nullable(changes["note"])
        if "payment_method_id" in changes:
            candidate["Pn"] = self._id(
                changes["payment_method_id"],
                "payment_method_id",
            )
        if "payment_reference" in changes:
            candidate["Pc"] = self._nullable(
                changes["payment_reference"]
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
        for field, attribute in (
            ("voucher", "Vo"),
            ("bank_reference", "Ba"),
        ):
            if field in changes:
                candidate[attribute] = self._nullable(changes[field])

        enforce_kind = bool(
            {"amount", "category_id", "subcategory_id"} & set(changes)
        )
        self._validate_transaction(
            candidate,
            enforce_category_kind=enforce_kind,
        )
        self.writer.replace_record(record.span, candidate)
        self.transactions[transaction_id] = candidate
        self.touched_transactions.add(transaction_id)
        return transaction_id

    def delete_transaction(self, operation: DeleteTransaction) -> str:
        transaction_id = self._id(
            operation.transaction_id,
            "transaction_id",
            allow_zero=False,
        )
        existing = self.transactions.get(transaction_id)
        record = self.index.transactions.get(transaction_id)
        if existing is None or record is None:
            raise RecordNotFoundError(
                "Transaction %s does not exist" % transaction_id
            )
        if transaction_id in self.touched_transactions:
            raise MutationConflictError(
                "Transaction %s is mutated more than once in one batch"
                % transaction_id
            )
        if self._protected_transaction(existing):
            raise MutationError(
                "Transfer and split transactions require their dedicated mutation phase"
            )
        for other_id, other in self.transactions.items():
            if other_id == transaction_id:
                continue
            if (
                other.get("Trt") == transaction_id
                or other.get("Mo") == transaction_id
            ):
                raise MutationError(
                    "Transaction %s is referenced by transaction %s"
                    % (transaction_id, other_id)
                )
        self.writer.delete(record.span)
        del self.transactions[transaction_id]
        self.touched_transactions.add(transaction_id)
        return transaction_id

    def apply(self, operation: MutationOperation) -> Tuple[str, str]:
        if isinstance(operation, CreateParty):
            return "Party", self.create_party(operation)
        if isinstance(operation, CreateCategory):
            return "Category", self.create_category(operation)
        if isinstance(operation, CreateSubcategory):
            return "Sub_category", self.create_subcategory(operation)
        if isinstance(operation, CreateTransaction):
            return "Transaction", self.create_transaction(operation)
        if isinstance(operation, UpdateTransaction):
            return "Transaction", self.update_transaction(operation)
        if isinstance(operation, DeleteTransaction):
            return "Transaction", self.delete_transaction(operation)
        raise MutationError(
            "Unsupported mutation operation %s" % type(operation).__name__
        )


class MutationEngine:
    """Apply an atomic batch of typed mutations to one immutable GSB document."""

    def __init__(self, document: GsbDocument):
        self.document = document

    def apply(
        self,
        operations: Iterable[MutationOperation],
        password: Optional[str] = None,
    ) -> MutationResult:
        assert_valid_document(self.document)
        session = _MutationSession(self.document)
        outcomes: List[MutationOutcome] = []
        for index, operation in enumerate(tuple(operations)):
            record_type, record_id = session.apply(operation)
            outcomes.append(
                MutationOutcome(
                    operation_index=index,
                    operation=type(operation).__name__,
                    record_type=record_type,
                    record_id=record_id,
                )
            )

        xml_bytes = session.writer.render_xml()
        result_document = parse_document(xml_bytes)
        assert_valid_document(result_document)
        raw_bytes = session.writer.render(password=password)
        return MutationResult(
            raw_bytes=raw_bytes,
            xml_bytes=xml_bytes,
            outcomes=tuple(outcomes),
        )


def apply_mutations(
    raw_bytes: bytes,
    operations: Iterable[MutationOperation],
    password: Optional[str] = None,
) -> MutationResult:
    document = parse_document(raw_bytes, password=password)
    return MutationEngine(document).apply(
        operations,
        password=password,
    )
