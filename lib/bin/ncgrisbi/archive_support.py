"""Grisbi-compatible archive listing and date-range selection.

All archive selection happens server-side against the complete document.
Browser requests never send transaction ID lists or duplicate financial data.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

from .errors import MutationError, RecordNotFoundError

_NULL = (None, "", "0", "(null)", "(NULL)")


def _date(value: str):
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except (TypeError, ValueError) as exc:
        raise MutationError("Archive dates must use valid MM/DD/YYYY values") from exc


def archive_rows(root: Any) -> list[dict[str, Any]]:
    totals: Dict[str, Dict[str, Dict[str, Any]]] = {}
    counts: Dict[str, int] = {}
    for tx in root.findall("Transaction"):
        archive_id = tx.get("Ar", "0")
        if archive_id in _NULL:
            continue
        account_id = tx.get("Ac") or ""
        item = totals.setdefault(archive_id, {}).setdefault(
            account_id, {"count": 0, "amount": Decimal("0")}
        )
        item["count"] += 1
        # Split children must not be double-counted in an archive summary.
        if tx.get("Mo", "0") in _NULL:
            item["amount"] += Decimal(tx.get("Am") or "0")
        counts[archive_id] = counts.get(archive_id, 0) + 1

    rows = []
    for entry in root.findall("Archive"):
        archive_id = entry.get("Nb")
        if not archive_id:
            continue
        rows.append({
            "id": archive_id,
            "name": entry.get("Na") or "",
            "startDate": None if entry.get("Bdte") in _NULL else entry.get("Bdte"),
            "endDate": None if entry.get("Edte") in _NULL else entry.get("Edte"),
            "financialYearId": None if entry.get("Fye") in _NULL else entry.get("Fye"),
            "reportTitle": None if entry.get("Rep") in _NULL else entry.get("Rep"),
            "count": counts.get(archive_id, 0),
            "accounts": {
                account: {"count": value["count"], "amount": str(value["amount"])}
                for account, value in totals.get(archive_id, {}).items()
            },
        })
    return rows


def date_archive_selection(root: Any, start_date: str, end_date: str) -> dict[str, Any]:
    start = _date(start_date)
    end = _date(end_date)
    if start > end:
        raise MutationError("The archive start date must not be after its end date")
    # Disallow crossing any existing date-based archive interval, including
    # intervals containing no current transactions.
    for archive in root.findall("Archive"):
        beginning, ending = archive.get("Bdte"), archive.get("Edte")
        if beginning not in _NULL and ending not in _NULL:
            if start <= _date(ending) and end >= _date(beginning):
                raise MutationError("This date range overlaps an existing Grisbi archive")

    tx_by_id = {
        tx.get("Nb"): tx
        for tx in root.findall("Transaction")
        if tx.get("Nb")
    }
    children: Dict[str, list[str]] = {}
    for tx in tx_by_id.values():
        mother = tx.get("Mo", "0")
        if mother not in _NULL:
            children.setdefault(mother, []).append(tx.get("Nb"))

    chosen: set[str] = set()
    queue: deque[str] = deque()
    for tx_id, tx in tx_by_id.items():
        if tx.get("Ar", "0") not in _NULL:
            continue
        date = _date(tx.get("Dt", ""))
        if start <= date <= end:
            chosen.add(tx_id)
            queue.append(tx_id)

    # Grisbi links both transfer halves and complete split groups. The
    # closure is validated before a single attribute is modified.
    while queue:
        tx_id = queue.popleft()
        tx = tx_by_id[tx_id]
        linked = []
        counterpart = tx.get("Trt", "0")
        mother = tx.get("Mo", "0")
        if counterpart not in _NULL:
            linked.append(counterpart)
        if mother not in _NULL:
            linked.append(mother)
        linked.extend(children.get(tx_id, []))
        for other_id in linked:
            other = tx_by_id.get(other_id)
            if other is None:
                raise MutationError("Archive selection contains a missing linked transaction")
            if other.get("Ar", "0") not in _NULL:
                raise MutationError("Archive selection links to an already archived transaction")
            if other_id not in chosen:
                chosen.add(other_id)
                queue.append(other_id)

    if not chosen:
        raise MutationError("No unarchived transactions fall in this date range")

    summaries: Dict[str, Dict[str, Any]] = {}
    for tx_id in chosen:
        tx = tx_by_id[tx_id]
        account_id = tx.get("Ac", "0")
        entry = summaries.setdefault(account_id, {"count": 0, "amount": Decimal("0")})
        entry["count"] += 1
        if tx.get("Mo", "0") in _NULL:
            entry["amount"] += Decimal(tx.get("Am") or "0")
    return {
        "startDate": start_date,
        "endDate": end_date,
        "count": len(chosen),
        "accounts": {
            account_id: {"count": value["count"], "amount": str(value["amount"])}
            for account_id, value in sorted(summaries.items())
        },
        "transactionIds": sorted(chosen, key=lambda value: int(value)),
    }


def archive_account_check(root: Any, archive_id: str) -> None:
    if not any(node.get("Nb") == archive_id for node in root.findall("Archive")):
        raise RecordNotFoundError("Archive %s does not exist" % archive_id)
