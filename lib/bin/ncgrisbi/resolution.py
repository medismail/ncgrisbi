from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .errors import MutationError
from .index import GsbIndex
from .mutations import (
    CreateCategory,
    CreateParty,
    CreateSubcategory,
    CreateTransaction,
    MutationOperation,
)

_WS_RE = re.compile(r"\s+", re.UNICODE)
_EXTENDED_TRANSACTION_FIELDS = {
    "partyName",
    "categoryName",
    "subcategoryName",
    "createMissing",
    "categoryKind",
}


class NameResolutionError(MutationError):
    """Raised when a human-readable Grisbi reference cannot be resolved safely."""


@dataclass(frozen=True)
class PlannedMutation:
    operation: MutationOperation
    client_operation_index: int
    role: str
    auto_created: bool = False


@dataclass(frozen=True)
class ResolutionPlan:
    mutations: Tuple[PlannedMutation, ...]

    @property
    def operations(self) -> Tuple[MutationOperation, ...]:
        return tuple(item.operation for item in self.mutations)


@dataclass(frozen=True)
class _NamedRecord:
    record_id: str
    display_name: str
    kind: Optional[int] = None


def clean_display_name(value: Any, record_type: str = "Record") -> str:
    if not isinstance(value, str):
        raise NameResolutionError("%s name must be text" % record_type)
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _WS_RE.sub(" ", normalized).strip()
    if not normalized:
        raise NameResolutionError("%s name cannot be empty" % record_type)
    if any(ord(char) < 32 for char in normalized):
        raise NameResolutionError(
            "%s name contains an unsupported control character" % record_type
        )
    return normalized


def normalize_name(value: Any, record_type: str = "Record") -> str:
    return clean_display_name(value, record_type).casefold()


def _attributes(record: Any) -> Mapping[str, str]:
    attributes = getattr(record, "attributes", record)
    if not isinstance(attributes, Mapping):
        raise NameResolutionError("Indexed Grisbi record has invalid attributes")
    return attributes


def _canonical_id(value: Any, field: str, allow_zero: bool = True) -> str:
    text = str(value)
    try:
        number = int(text)
    except (TypeError, ValueError):
        raise NameResolutionError("%s must be a numeric Grisbi identifier" % field)
    if number < 0 or (number == 0 and not allow_zero) or str(number) != text:
        raise NameResolutionError("%s is not a canonical Grisbi identifier" % field)
    return text


def _decimal_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise NameResolutionError("Amount is not a valid decimal number")
    if not amount.is_finite():
        raise NameResolutionError("Amount must be finite")
    return amount


def _category_kind_for_amount(amount: Decimal) -> Optional[int]:
    if amount < 0:
        return 1
    if amount > 0:
        return 0
    return None


class ResolutionPlanner:
    """Expand name-based transaction references into Phase 2 typed mutations.

    The planner predicts server-side IDs using the same maximum-plus-one rules as
    ``MutationEngine``. The complete expanded batch is then applied once, so a
    validation failure produces no output bytes and no partial record creation.
    """

    def __init__(
        self,
        index: GsbIndex,
        decode_base_operation: Callable[[Mapping[str, Any]], MutationOperation],
    ) -> None:
        self.index = index
        self.decode_base_operation = decode_base_operation
        self.planned: List[PlannedMutation] = []

        self.party_names: Dict[str, List[_NamedRecord]] = {}
        self.category_names: Dict[str, List[_NamedRecord]] = {}
        self.subcategory_names: Dict[Tuple[str, str], List[_NamedRecord]] = {}
        self.categories_by_id: Dict[str, _NamedRecord] = {}

        for record_id, record in index.parties.items():
            attrs = _attributes(record)
            self._register_party(record_id, attrs.get("Na", ""))
        for record_id, record in index.categories.items():
            attrs = _attributes(record)
            try:
                kind = int(attrs.get("Kd", ""))
            except (TypeError, ValueError):
                kind = None
            self._register_category(record_id, attrs.get("Na", ""), kind)
        for (category_id, record_id), record in index.subcategories.items():
            attrs = _attributes(record)
            self._register_subcategory(category_id, record_id, attrs.get("Na", ""))

        self.next_party = int(index.next_party_id())
        self.next_category = int(index.next_category_id())
        self.next_subcategories: Dict[str, int] = {}

    @staticmethod
    def _append_named(
        registry: Dict[Any, List[_NamedRecord]],
        key: Any,
        candidate: _NamedRecord,
    ) -> None:
        registry.setdefault(key, []).append(candidate)

    def _register_party(self, record_id: str, name: Any) -> None:
        display = clean_display_name(name, "Party")
        self._append_named(
            self.party_names,
            normalize_name(display, "Party"),
            _NamedRecord(str(record_id), display),
        )

    def _register_category(
        self,
        record_id: str,
        name: Any,
        kind: Optional[int],
    ) -> None:
        display = clean_display_name(name, "Category")
        candidate = _NamedRecord(str(record_id), display, kind)
        self._append_named(
            self.category_names,
            normalize_name(display, "Category"),
            candidate,
        )
        self.categories_by_id[str(record_id)] = candidate

    def _register_subcategory(
        self,
        category_id: str,
        record_id: str,
        name: Any,
    ) -> None:
        display = clean_display_name(name, "Subcategory")
        key = (str(category_id), normalize_name(display, "Subcategory"))
        self._append_named(
            self.subcategory_names,
            key,
            _NamedRecord(str(record_id), display),
        )

    def _append(
        self,
        operation: MutationOperation,
        client_index: int,
        role: str,
        auto_created: bool = False,
    ) -> None:
        self.planned.append(
            PlannedMutation(
                operation=operation,
                client_operation_index=client_index,
                role=role,
                auto_created=auto_created,
            )
        )

    @staticmethod
    def _single_match(
        matches: Sequence[_NamedRecord],
        record_type: str,
        display_name: str,
    ) -> Optional[_NamedRecord]:
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ids = ", ".join(candidate.record_id for candidate in matches)
            raise NameResolutionError(
                "%s name %r is ambiguous; matching IDs: %s"
                % (record_type, display_name, ids)
            )
        return None

    def _allocate_subcategory(self, category_id: str) -> str:
        if category_id not in self.next_subcategories:
            self.next_subcategories[category_id] = int(
                self.index.next_subcategory_id(category_id)
            )
        allocated = self.next_subcategories[category_id]
        self.next_subcategories[category_id] += 1
        return str(allocated)

    def _resolve_party(
        self,
        name: Any,
        create_missing: bool,
        client_index: int,
    ) -> str:
        display = clean_display_name(name, "Party")
        key = normalize_name(display, "Party")
        match = self._single_match(self.party_names.get(key, ()), "Party", display)
        if match is not None:
            return match.record_id
        if not create_missing:
            raise NameResolutionError("Party %r does not exist" % display)

        record_id = str(self.next_party)
        self.next_party += 1
        operation = CreateParty(name=display)
        self._append(operation, client_index, "party", auto_created=True)
        self._register_party(record_id, display)
        return record_id

    def _resolve_category(
        self,
        name: Any,
        amount: Decimal,
        requested_kind: Optional[int],
        create_missing: bool,
        client_index: int,
    ) -> str:
        display = clean_display_name(name, "Category")
        key = normalize_name(display, "Category")
        amount_kind = _category_kind_for_amount(amount)

        if requested_kind is not None:
            if not isinstance(requested_kind, int) or isinstance(requested_kind, bool):
                raise NameResolutionError("categoryKind must be a JSON integer")
            if requested_kind not in (0, 1):
                raise NameResolutionError("categoryKind must be 0 (credit) or 1 (debit)")
            if amount_kind is not None and requested_kind != amount_kind:
                raise NameResolutionError(
                    "categoryKind does not match the transaction amount direction"
                )

        desired_kind = amount_kind if amount_kind is not None else requested_kind
        all_matches = list(self.category_names.get(key, ()))
        normal_matches = [match for match in all_matches if match.kind in (0, 1)]
        matches = (
            [match for match in normal_matches if match.kind == desired_kind]
            if desired_kind is not None
            else normal_matches
        )
        match = self._single_match(matches, "Category", display)
        if match is not None:
            return match.record_id

        if all_matches:
            if desired_kind is None:
                raise NameResolutionError(
                    "Category %r is ambiguous; provide categoryKind or categoryId"
                    % display
                )
            raise NameResolutionError(
                "Category %r exists but not with kind %d" % (display, desired_kind)
            )
        if not create_missing:
            raise NameResolutionError("Category %r does not exist" % display)
        if desired_kind is None:
            raise NameResolutionError(
                "categoryKind is required to create a category for a zero amount"
            )

        record_id = str(self.next_category)
        self.next_category += 1
        operation = CreateCategory(name=display, kind=desired_kind)
        self._append(operation, client_index, "category", auto_created=True)
        self._register_category(record_id, display, desired_kind)
        return record_id

    def _validate_category_id_kind(
        self,
        category_id: str,
        amount: Decimal,
        requested_kind: Optional[int],
    ) -> None:
        category = self.categories_by_id.get(category_id)
        if category is None:
            raise NameResolutionError("Category ID %s does not exist" % category_id)
        if category.kind == 2:
            raise NameResolutionError(
                "Special categories are reserved for transfer/split transactions"
            )
        amount_kind = _category_kind_for_amount(amount)
        desired_kind = amount_kind if amount_kind is not None else requested_kind
        if requested_kind is not None:
            if not isinstance(requested_kind, int) or isinstance(requested_kind, bool):
                raise NameResolutionError("categoryKind must be a JSON integer")
            if requested_kind not in (0, 1):
                raise NameResolutionError("categoryKind must be 0 (credit) or 1 (debit)")
            if amount_kind is not None and requested_kind != amount_kind:
                raise NameResolutionError(
                    "categoryKind does not match the transaction amount direction"
                )
        if desired_kind is not None and category.kind != desired_kind:
            raise NameResolutionError(
                "Category ID %s does not match the transaction amount direction"
                % category_id
            )

    def _resolve_subcategory(
        self,
        category_id: str,
        name: Any,
        create_missing: bool,
        client_index: int,
    ) -> str:
        if category_id == "0":
            raise NameResolutionError(
                "A subcategory name cannot be used without a category"
            )
        if category_id not in self.categories_by_id:
            raise NameResolutionError("Category ID %s does not exist" % category_id)

        display = clean_display_name(name, "Subcategory")
        key = (category_id, normalize_name(display, "Subcategory"))
        match = self._single_match(
            self.subcategory_names.get(key, ()),
            "Subcategory",
            display,
        )
        if match is not None:
            return match.record_id
        if not create_missing:
            raise NameResolutionError(
                "Subcategory %r does not exist in category %s"
                % (display, category_id)
            )

        record_id = self._allocate_subcategory(category_id)
        operation = CreateSubcategory(category_id=category_id, name=display)
        self._append(operation, client_index, "subcategory", auto_created=True)
        self._register_subcategory(category_id, record_id, display)
        return record_id

    def _track_direct_create(
        self,
        operation: MutationOperation,
        client_index: int,
    ) -> None:
        if isinstance(operation, CreateParty):
            record_id = str(self.next_party)
            self.next_party += 1
            self._register_party(record_id, operation.name)
        elif isinstance(operation, CreateCategory):
            record_id = str(self.next_category)
            self.next_category += 1
            self._register_category(record_id, operation.name, operation.kind)
        elif isinstance(operation, CreateSubcategory):
            category_id = _canonical_id(
                operation.category_id,
                "categoryId",
                allow_zero=False,
            )
            record_id = self._allocate_subcategory(category_id)
            self._register_subcategory(category_id, record_id, operation.name)

    def _plan_resolved_transaction(
        self,
        raw: Mapping[str, Any],
        client_index: int,
    ) -> None:
        create_missing = raw.get("createMissing", False)
        if not isinstance(create_missing, bool):
            raise NameResolutionError("createMissing must be a JSON boolean")

        party_name_present = "partyName" in raw
        category_name_present = "categoryName" in raw
        subcategory_name_present = "subcategoryName" in raw
        if party_name_present and "partyId" in raw:
            raise NameResolutionError("Use either partyId or partyName, not both")
        if category_name_present and "categoryId" in raw:
            raise NameResolutionError("Use either categoryId or categoryName, not both")
        if subcategory_name_present and "subcategoryId" in raw:
            raise NameResolutionError(
                "Use either subcategoryId or subcategoryName, not both"
            )

        if "amount" not in raw:
            # The base decoder will produce the canonical missing-field message.
            amount = Decimal("0")
        else:
            amount = _decimal_amount(raw["amount"])
        requested_kind = raw.get("categoryKind")

        translated = dict(raw)
        for field in _EXTENDED_TRANSACTION_FIELDS:
            translated.pop(field, None)

        if party_name_present:
            translated["partyId"] = self._resolve_party(
                raw["partyName"],
                create_missing,
                client_index,
            )

        if category_name_present:
            category_id = self._resolve_category(
                raw["categoryName"],
                amount,
                requested_kind,
                create_missing,
                client_index,
            )
            translated["categoryId"] = category_id
        else:
            category_id = _canonical_id(raw.get("categoryId", "0"), "categoryId")
            if category_id != "0":
                self._validate_category_id_kind(category_id, amount, requested_kind)
            elif requested_kind is not None:
                raise NameResolutionError(
                    "categoryKind requires categoryName or categoryId"
                )

        if subcategory_name_present:
            translated["subcategoryId"] = self._resolve_subcategory(
                category_id,
                raw["subcategoryName"],
                create_missing,
                client_index,
            )

        operation = self.decode_base_operation(translated)
        if not isinstance(operation, CreateTransaction):
            raise NameResolutionError(
                "Name resolution is supported only for createTransaction"
            )
        self._append(operation, client_index, "transaction")

    def plan(self, raw_operations: Iterable[Mapping[str, Any]]) -> ResolutionPlan:
        for client_index, raw in enumerate(raw_operations):
            if not isinstance(raw, Mapping):
                raise NameResolutionError(
                    "Every mutation operation must be a JSON object"
                )
            operation_type = raw.get("type")
            extended = operation_type == "createTransaction" and bool(
                set(raw) & _EXTENDED_TRANSACTION_FIELDS
            )
            if extended:
                self._plan_resolved_transaction(raw, client_index)
                continue

            operation = self.decode_base_operation(raw)
            self._append(operation, client_index, "primary")
            self._track_direct_create(operation, client_index)

        return ResolutionPlan(tuple(self.planned))


def plan_operations(
    document: Any,
    raw_operations: Iterable[Mapping[str, Any]],
    decode_base_operation: Callable[[Mapping[str, Any]], MutationOperation],
) -> ResolutionPlan:
    return ResolutionPlanner(
        GsbIndex.build(document),
        decode_base_operation,
    ).plan(raw_operations)
