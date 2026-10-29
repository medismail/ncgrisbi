"""Read-only Grisbi category reports.

Only settings with verified semantics are executed. A report with unsupported
filters must fail explicitly rather than display misleading financial totals.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from .errors import MutationError, RecordNotFoundError
from .model import GsbDocument
from .read import _ReadContext

_NULL = ("", "0", "(null)", "(NULL)")
_SUPPORTED_ZERO = (
    "Budget_use", "Payee_use", "Account_use_selection",
    "Financial_year_used", "Use_text", "Use_amount",
    "Payment_method_use", "Categ_use_selection", "Split_by_date",
    "Split_by_fin_year", "Account_group_transactions",
)
_ONE_OR_UNSET = ("Categ_use", "Categ_show_sub_categ")
_DATE_FORMAT = "%m/%d/%Y"


def _value(element: Any, key: str, default: str = "0") -> str:
    return element.get(key, default)


def _date(raw: Optional[str]) -> Optional[date]:
    if not raw or raw in _NULL:
        return None
    try:
        return datetime.strptime(raw, _DATE_FORMAT).date()
    except ValueError as exc:
        raise MutationError("Invalid Grisbi report or transaction date") from exc


def _months_before(today: date, months: int) -> date:
    month_index = today.year * 12 + today.month - 1 - months
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def _period(report: Any, today: date) -> tuple[Optional[date], Optional[date]]:
    kind = _value(report, "Date_kind", "0")
    if kind == "0":
        return None, None
    if kind == "1":
        start, end = _date(report.get("Date_beginning")), _date(report.get("Date_end"))
        if start is None or end is None or start > end:
            raise MutationError("Report custom date range is incomplete")
        return start, end
    if kind == "2":
        return None, today
    if kind in ("3", "5"):
        return today.replace(day=1), today if kind == "5" else date(
            today.year, today.month, calendar.monthrange(today.year, today.month)[1]
        )
    if kind in ("4", "6"):
        return date(today.year, 1, 1), today if kind == "6" else date(today.year, 12, 31)
    if kind == "7":
        last_month = _months_before(today.replace(day=1), 1)
        return last_month, date(last_month.year, last_month.month,
                                calendar.monthrange(last_month.year, last_month.month)[1])
    if kind == "8":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if kind == "9":
        return today - timedelta(days=30), today
    if kind in ("10", "11", "12"):
        return _months_before(today, {"10": 3, "11": 6, "12": 12}[kind]), today
    raise MutationError("Unsupported Grisbi report date kind: %s" % kind)


def _amount(raw: Optional[str]) -> Decimal:
    try:
        amount = Decimal(raw or "0")
    except InvalidOperation as exc:
        raise MutationError("Invalid transaction amount in report") from exc
    if not amount.is_finite():
        raise MutationError("Invalid non-finite transaction amount in report")
    return amount


def _money(value: Decimal) -> str:
    return format(value, "f")


def _leaf(name: str) -> Dict[str, Any]:
    return {"name": name, "count": 0, "amount": Decimal("0"), "transactions": []}


def _validate(report: Any) -> None:
    for key in _SUPPORTED_ZERO:
        if _value(report, key) != "0":
            raise MutationError("Unsupported Grisbi report option: %s" % key)
    for key in _ONE_OR_UNSET:
        if _value(report, key, "1") != "1":
            raise MutationError("This report requires category/subcategory grouping: %s" % key)
    if _value(report, "Show_split_amounts") != "1":
        raise MutationError("This report does not separate income and expenses")
    if _value(report, "Transfer_kind") not in ("0", "1", "2"):
        raise MutationError("Unsupported transfer selection in report")
    if _value(report, "Date_select_value") not in ("0", "1"):
        raise MutationError("Unsupported report date selection")
    if _value(report, "General_sort_type", "1/-/2/-/3/-/4/-/5/-/6").split("/-/")[0] != "1":
        raise MutationError("Unsupported Grisbi report sorting order")
    if _value(report, "Categ_currency", "1") != _value(report, "Currency_general", "1"):
        raise MutationError("Report uses different category and total currencies")


def report_snapshot(document: GsbDocument, report_id: str, today: Optional[date] = None) -> Dict[str, Any]:
    """Run a saved category report without modifying the document."""
    report = next((r for r in document.root.findall("Report") if r.get("Nb") == report_id), None)
    if report is None:
        raise RecordNotFoundError("Report %s does not exist" % report_id)
    _validate(report)
    today = today or date.today()
    start, end = _period(report, today)
    context = _ReadContext(document)
    currency_id = _value(report, "Currency_general", "1")
    currency = context.currencies.get(currency_id)
    if currency is None:
        raise MutationError("Report references an unknown currency")
    code = currency.get("Ico") or "Unknown"

    # Grisbi has one category and at most one subcategory per transaction.
    categories: Dict[str, Dict[str, Any]] = {}
    for cat in context.category_rows:
        cid = cat.get("Nb") or ""
        categories[cid] = {
            "name": cat.get("Na") or "", "kind": cat.get("Kd") or "0",
            "subcategories": {},
        }
    subnames = {
        (e.get("Nbc"), e.get("Nb")): e.get("Na") or ""
        for e in context.subcategory_rows
    }
    sections = {
        "income": {"categories": {}, "uncategorized": _leaf("No category")},
        "expenses": {"categories": {}, "uncategorized": _leaf("No category")},
    }
    rows = []
    transfer_choice = _value(report, "Transfer_kind")
    show_parent = _value(report, "Show_exclude_split_child") == "1"
    ignore_archives = _value(report, "Ignore_archives") == "1"
    use_value_date = _value(report, "Date_select_value") == "1"

    for tx in context.transaction_rows:
        # Include one amount per split: either parent or children, never both.
        if tx.get("Mo", "0") not in _NULL and show_parent:
            continue
        if tx.get("Br", "0") not in _NULL and not show_parent:
            continue
        if ignore_archives and tx.get("Ar", "0") not in _NULL:
            continue
        transfer_id = tx.get("Trt", "0")
        if transfer_id not in _NULL:
            # Grisbi transfer choice 2 without account selection rejects transfers.
            if transfer_choice in ("0", "2"):
                continue
            other = context.transactions.get(transfer_id)
            if other is None or other.get("Trt") != tx.get("Nb"):
                raise MutationError("Report contains an unresolved transfer")
            target = context.accounts.get(other.get("Ac") or "")
            if target is None or target.get("Kind") not in ("2", "3"):
                continue
        transaction_date = _date(tx.get("Dt"))
        value_date = _date(tx.get("Dv")) if use_value_date else None
        when = value_date or transaction_date
        if when is None or (start is not None and when < start) or (end is not None and when > end):
            continue
        account = context.accounts.get(tx.get("Ac") or "")
        if account is None:
            raise MutationError("Report transaction references missing account")
        tx_currency = tx.get("Cu") or account.get("Currency") or ""
        if tx_currency != currency_id:
            raise MutationError("Report requires currency conversion not yet supported")
        amount = _amount(tx.get("Am"))
        category_id = tx.get("Ca", "0")
        category = categories.get(category_id)
        section_name = ("expenses" if category["kind"] != "0" else "income") if category else (
            "expenses" if amount < 0 else "income"
        )
        section = sections[section_name]
        display_amount = -amount if section_name == "expenses" else amount
        if category is None:
            if category_id not in _NULL:
                raise MutationError("Report references an unknown category")
            leaf = section["uncategorized"]
        else:
            grouped = section["categories"].setdefault(category_id, {
                "name": category["name"], "subcategories": {},
            })
            sub_id = tx.get("Sca", "0")
            if sub_id not in _NULL and (category_id, sub_id) not in subnames:
                raise MutationError("Report references an unknown subcategory")
            leaf = grouped["subcategories"].setdefault(sub_id, _leaf(
                subnames.get((category_id, sub_id), "No subcategory")
            ))
        party = context.parties.get(tx.get("Pa") or "")
        index = len(rows)
        rows.append({
            "id": tx.get("Nb") or "", "accountId": tx.get("Ac") or "",
            "date": tx.get("Dt") or "", "payee": party.get("Na") if party is not None else "",
            "amount": _money(amount),
        })
        leaf["transactions"].append(index)
        leaf["count"] += 1
        leaf["amount"] += display_amount

    def finish(section: Dict[str, Any]) -> Dict[str, Any]:
        result = []
        total = Decimal("0")
        count = 0
        # Preserve Grisbi category/subcategory name sorting; 'No subcategory' is last.
        for category in sorted(section["categories"].values(), key=lambda c: c["name"].casefold()):
            leaves = category["subcategories"]
            children = [leaves[key] for key in sorted(
                (key for key in leaves if key not in _NULL),
                key=lambda key: leaves[key]["name"].casefold()
            )]
            children.extend(leaves[key] for key in leaves if key in _NULL)
            cat_amount = sum((leaf["amount"] for leaf in children), Decimal("0"))
            cat_count = sum(leaf["count"] for leaf in children)
            result.append({
                "name": category["name"], "count": cat_count,
                "amount": _money(cat_amount),
                "subcategories": [
                    {**leaf, "amount": _money(leaf["amount"])} for leaf in children
                ],
            })
            total += cat_amount
            count += cat_count
        missing = section["uncategorized"]
        total += missing["amount"]
        count += missing["count"]
        return {
            "categories": result,
            "uncategorized": ({**missing, "amount": _money(missing["amount"])}
                              if missing["count"] else None),
            "count": count,
            "total": _money(total),
        }

    income = finish(sections["income"])
    expenses = finish(sections["expenses"])
    return {
        "currency": code,
        "period": {
            "from": start.isoformat() if start is not None else None,
            "to": end.isoformat() if end is not None else None,
        },
        "income": income,
        "expenses": expenses,
        "difference": _money(Decimal(income["total"]) - Decimal(expenses["total"])),
        "transactions": rows,
    }
