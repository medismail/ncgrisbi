# Phase 2: validated mutation engine

Phase 2 adds typed, atomic mutations on top of the Phase 1 lossless writer. It
still does not replace the Nextcloud controller or the legacy `grisbi.py`
command protocol; that integration remains a later phase.

## Guarantees implemented

- Every input document is semantically validated before a mutation batch starts.
- Every rendered XML document is parsed and semantically validated again before
  its original compression/encryption envelope is restored.
- Transaction, party, category, and subcategory identifiers are allocated by the
  server from the maximum numeric identifier currently present, never from XML
  order and never from a client-provided identifier.
- A mutation batch is atomic: an invalid operation raises an exception and the
  immutable source document remains unchanged.
- Transaction updates are partial. Unspecified GSB attributes are copied from the
  original transaction, preserving imported IDs, value dates, reconciliation,
  financial-year data, budgets, vouchers, bank references, and other metadata.
- Normal transaction creation validates account, currency, party, category,
  subcategory, payment-method, date, marked-state, amount precision, and
  debit/credit category direction.
- Transfer and split fields (`Br`, `Trt`, `Mo`) cannot be created, edited, or
  deleted through the normal-transaction API. Their reciprocal multi-record
  semantics remain reserved for the dedicated transfer and split phases.
- Multiple mutations of the same existing transaction in one batch are rejected
  rather than producing overlapping byte patches.

## Public operations

- `CreateParty`
- `CreateCategory`
- `CreateSubcategory`
- `CreateTransaction`
- `UpdateTransaction`
- `DeleteTransaction`

`MutationEngine.apply()` accepts an iterable of these typed operations and
returns `MutationResult`, containing the envelope-preserving bytes, the patched
XML bytes, and one server-generated `MutationOutcome` per operation.

`apply_mutations()` is the convenience entry point for callers that have raw GSB
bytes rather than an already parsed document.

## Validation profile

The validator reports structured `ValidationIssue` values and checks:

- exactly one `General` record and GSB file version 1.2.1;
- canonical required attributes for supported mutable records;
- unique record identifiers;
- valid account, currency, party, category, subcategory, and payment references;
- decimal transaction amounts;
- reciprocal transfer references;
- existing split-mother references;
- valid category kinds and currency precision.

The validator deliberately does not require financial-year or budget records for
all `Fi`, `Bu`, or `Sbu` values because historical Grisbi files can retain those
numeric values after related configuration records have been removed.

## Modules

- `index.py`: exact record/span indexes and maximum-ID allocation.
- `validator.py`: structured semantic validation.
- `mutations.py`: typed operations, domain checks, atomic planning, and results.
- `errors.py`: validation and mutation-specific exception types.

## Phase boundary

Phase 2 exposes a Python API only. The Nextcloud controller, ETag concurrency,
CSRF changes, secure password transport, and replacement of the legacy command
path belong to Phase 3. Automatic name resolution and create-if-missing party or
category behaviour belongs to Phase 4.
