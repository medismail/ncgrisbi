from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ._mutation_core import (
    NULLS,
    Phase6Result as MutationResult,
    Phase6Session as MutationCoreSession,
    _bool,
    _canonical_id,
    _clean_name,
    _date,
    _name_key,
    _nullable,
    _required,
    _strict_fields,
)
from .errors import MutationError
from .formats import SupportLevel
from .parser import parse_document
from .validator import assert_valid_document, warning_issues


class MutationSession(MutationCoreSession):
    """Canonical batch mutation session with format-owned creation defaults."""

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

        # Parser spans and root children have already been proven to align. Build
        # all mutation indexes in one pass instead of scanning each tag twice.
        for element, span in zip(document.root, document.spans):
            tag = element.tag
            attributes = dict(element.attrib)
            if tag == "Account":
                key = element.get("Number")
                if key:
                    self.accounts[key] = attributes
            elif tag == "Currency":
                key = element.get("Nb")
                if key:
                    self.currencies[key] = attributes
            elif tag == "Payment":
                key = element.get("Number")
                if key:
                    self.payments[key] = attributes
            elif tag == "Party":
                key = element.get("Nb")
                if key:
                    self.parties[key] = attributes
            elif tag == "Category":
                key = element.get("Nb")
                if key:
                    self.categories[key] = attributes
            elif tag == "Sub_category":
                parent = element.get("Nbc")
                key = element.get("Nb")
                if parent and key:
                    self.subcategories[(parent, key)] = attributes
            elif tag == "Transaction":
                key = element.get("Nb")
                if key:
                    self.transactions[key] = attributes
                    self.original_transactions[key] = dict(attributes)
                    self.transaction_spans[key] = span

        self.next_party = self._next_id(self.parties)
        self.next_category = self._next_id(self.categories)
        self.next_transaction = self._next_id(self.transactions)
        self.next_subcategories: Dict[str, int] = {}
        self.new_records: List[Tuple[str, Dict[str, str]]] = []
        self.new_transaction_ids: List[str] = []
        self.deleted_transactions: set[str] = set()
        self.structural_touched: set[str] = set()
        self.outcomes: List[Dict[str, Any]] = []

    def _new_record(self, tag: str, **values: Any) -> Dict[str, str]:
        profile = self.document.format_profile
        if profile is None:
            raise MutationError("The parsed document has no format profile")
        attributes = profile.defaults_for(tag)
        attributes.update({name: str(value) for name, value in values.items()})
        return attributes

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
        attributes = self._new_record("Party", Nb=party_id, Na=display)
        self.parties[party_id] = attributes
        self.new_records.append(("Party", attributes))
        self._outcome(
            client_index,
            "CreateParty",
            "Party",
            party_id,
            "party",
            True,
        )
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
            if (
                not isinstance(requested_kind, int)
                or isinstance(requested_kind, bool)
                or requested_kind not in (0, 1)
            ):
                raise MutationError("categoryKind must be 0 (credit) or 1 (debit)")
            if expected_kind is not None and str(requested_kind) != expected_kind:
                raise MutationError(
                    "categoryKind does not match the transaction amount direction"
                )
        desired_kind = (
            expected_kind
            if expected_kind is not None
            else str(requested_kind) if requested_kind is not None else None
        )

        if "categoryId" in raw:
            category_id = _canonical_id(
                raw.get("categoryId", "0"),
                "categoryId",
                allow_zero=True,
            )
            if category_id != "0":
                category = self.categories.get(category_id)
                if category is None:
                    raise MutationError("Unknown category %s" % category_id)
                if category.get("Kd") == "2":
                    raise MutationError(
                        "Special categories are reserved for breakdown transactions"
                    )
                if desired_kind is not None and category.get("Kd") != desired_kind:
                    raise MutationError(
                        "Category does not match the transaction amount direction"
                    )
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
                    raise MutationError(
                        "Category %r exists but not with the required kind" % display
                    )
                if not allow_create or not _bool(raw, "createMissing", False):
                    raise MutationError("Category %r does not exist" % display)
                if desired_kind is None:
                    raise MutationError("categoryKind is required for a zero amount")
                category_id = str(self.next_category)
                self.next_category += 1
                attributes = self._new_record(
                    "Category",
                    Nb=category_id,
                    Na=display,
                    Kd=desired_kind,
                )
                self.categories[category_id] = attributes
                self.new_records.append(("Category", attributes))
                self._outcome(
                    client_index,
                    "CreateCategory",
                    "Category",
                    category_id,
                    "category",
                    True,
                )
        else:
            if requested_kind is not None:
                raise MutationError("categoryKind requires categoryName or categoryId")
            category_id = "0"

        if category_id == "0":
            if raw.get("subcategoryId") not in NULLS or raw.get(
                "subcategoryName"
            ) not in (None, ""):
                raise MutationError("A subcategory cannot be used without a category")
            return "0", "0"

        if "subcategoryId" in raw:
            subcategory_id = _canonical_id(
                raw.get("subcategoryId", "0"),
                "subcategoryId",
                allow_zero=True,
            )
            if (
                subcategory_id != "0"
                and (category_id, subcategory_id) not in self.subcategories
            ):
                raise MutationError(
                    "Unknown subcategory %s/%s" % (category_id, subcategory_id)
                )
            return category_id, subcategory_id
        if "subcategoryName" not in raw or raw.get("subcategoryName") in (None, ""):
            return category_id, "0"
        display = _clean_name(raw["subcategoryName"], "Subcategory")
        key = display.casefold()
        matches = [
            number
            for (parent, number), attrs in self.subcategories.items()
            if parent == category_id
            and _name_key(attrs.get("Na", ""), "Subcategory") == key
        ]
        if len(matches) > 1:
            raise MutationError(
                "Subcategory %r is ambiguous in category %s"
                % (display, category_id)
            )
        if matches:
            return category_id, matches[0]
        if not allow_create or not _bool(raw, "createMissing", False):
            raise MutationError(
                "Subcategory %r does not exist in category %s"
                % (display, category_id)
            )
        subcategory_id = self._allocate_subcategory(category_id)
        attributes = self._new_record(
            "Sub_category",
            Nbc=category_id,
            Nb=subcategory_id,
            Na=display,
        )
        self.subcategories[(category_id, subcategory_id)] = attributes
        self.new_records.append(("Sub_category", attributes))
        self._outcome(
            client_index,
            "CreateSubcategory",
            "Sub_category",
            subcategory_id,
            "subcategory",
            True,
            categoryId=category_id,
        )
        return category_id, subcategory_id

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
        if (
            not isinstance(marked, int)
            or isinstance(marked, bool)
            or marked not in (0, 1, 2, 3)
        ):
            raise MutationError("marked must be an integer between 0 and 3")
        profile = self.document.format_profile
        if profile is None:
            raise MutationError("The parsed document has no format profile")
        attributes = profile.new_transaction_attributes(
            account_id=account_id,
            transaction_id=transaction_id,
            date=_date(_required(raw, "date")),
            value_date=_date(raw.get("valueDate"), "valueDate", allow_null=True),
            currency_id=currency_id,
            amount=amount_text,
            party_id=party_id,
            payment_id=payment_id,
        )
        attributes.update(
            {
                "Id": _nullable(raw.get("importedId")),
                "No": _nullable(raw.get("note")),
                "Pc": _nullable(raw.get("paymentReference")),
                "Ma": str(marked),
                "Fi": str(raw.get("financialYear", "0")),
                "Bu": str(raw.get("budgetId", "0")),
                "Sbu": str(raw.get("subbudgetId", "0")),
                "Vo": _nullable(raw.get("voucher")),
                "Ba": _nullable(raw.get("bankReference")),
            }
        )
        return attributes

    def create_party(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("name", "text", "search", "ignoreCase", "useRegex"))
        party_id = str(self.next_party)
        self.next_party += 1
        attributes = self._new_record(
            "Party",
            Nb=party_id,
            Na=_clean_name(_required(raw, "name"), "Party"),
            Txt=_nullable(raw.get("text")),
            Search=_nullable(raw.get("search")),
            IgnCase="1" if _bool(raw, "ignoreCase", False) else "0",
            UseRegex="1" if _bool(raw, "useRegex", False) else "0",
        )
        self.parties[party_id] = attributes
        self.new_records.append(("Party", attributes))
        self._outcome(client_index, "CreateParty", "Party", party_id)

    def create_category(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("name", "kind"))
        kind = _required(raw, "kind")
        if (
            not isinstance(kind, int)
            or isinstance(kind, bool)
            or kind not in (0, 1, 2)
        ):
            raise MutationError("kind must be 0, 1, or 2")
        category_id = str(self.next_category)
        self.next_category += 1
        attributes = self._new_record(
            "Category",
            Nb=category_id,
            Na=_clean_name(_required(raw, "name"), "Category"),
            Kd=str(kind),
        )
        self.categories[category_id] = attributes
        self.new_records.append(("Category", attributes))
        self._outcome(client_index, "CreateCategory", "Category", category_id)

    def create_subcategory(self, raw: Mapping[str, Any], client_index: int) -> None:
        _strict_fields(raw, ("categoryId", "name"))
        category_id = _canonical_id(_required(raw, "categoryId"), "categoryId")
        if category_id not in self.categories:
            raise MutationError("Unknown category %s" % category_id)
        subcategory_id = self._allocate_subcategory(category_id)
        attributes = self._new_record(
            "Sub_category",
            Nbc=category_id,
            Nb=subcategory_id,
            Na=_clean_name(_required(raw, "name"), "Subcategory"),
        )
        self.subcategories[(category_id, subcategory_id)] = attributes
        self.new_records.append(("Sub_category", attributes))
        self._outcome(
            client_index,
            "CreateSubcategory",
            "Sub_category",
            subcategory_id,
            categoryId=category_id,
        )


def apply_mutations(
    raw_bytes: bytes,
    raw_operations: Iterable[Mapping[str, Any]],
    password: Optional[str] = None,
) -> MutationResult:
    operations = tuple(raw_operations)
    if not operations:
        raise MutationError("operations cannot be empty")
    if len(operations) > 1000:
        raise MutationError("Mutation batch exceeds the operation limit")

    document = parse_document(raw_bytes, password=password)
    profile = document.format_profile
    if profile is None or profile.support_level is not SupportLevel.READ_WRITE:
        raise MutationError(
            "GSB file version %s is read-only" % document.file_version
        )

    session = MutationSession(document)
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
    return MutationResult(
        output,
        tuple(session.outcomes),
        warnings,
        changed_records,
    )


__all__ = ["MutationResult", "MutationSession", "apply_mutations"]
