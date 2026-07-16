# Phase 6: transfer hardening and quick bank checking

Phase 6 completes the same-currency transfer workflow already introduced in the revised Phase 5. It does not add cross-currency transfers or split/breakdown editing.

## Scope

Implemented:

- one mutation session for the complete HTTP batch;
- reciprocal transfer creation, update and deletion from either account side;
- safeguards for reconciled transfer data;
- non-fatal compatibility warnings for damaged historical transfer links;
- conversion of a normal transaction to a transfer and back;
- fast batch checked/unchecked changes through `setTransactionMarks`;
- compact exposure of Grisbi transaction-view preferences;
- tests using a file produced by Grisbi 1.2.2.

Deferred:

- cross-currency transfers and exchange-rate fields;
- split/breakdown transaction editing;
- the final responsive desktop/mobile transaction layout.

## Single-pass mutation session

The Phase 5 protocol previously reparsed and re-encoded the document after every client operation. Phase 6 now performs this sequence:

1. decode the gzip/encryption envelope once;
2. parse and validate the document once;
3. build mutable indexes for accounts, currencies, payments, references and transactions;
4. apply every normal, transfer, conversion and mark operation to the same session;
5. queue surgical patches against the original XML;
6. render one final XML document;
7. perform one final semantic verification;
8. encode the original envelope once;
9. let the Nextcloud service perform its existing single file write.

A mixed batch can therefore contain normal transactions, reciprocal transfers and quick marks without a parse/write cycle per row.

## Same-currency transfers

A valid transfer remains two ordinary Grisbi `Transaction` records:

- each transaction has `Ca=0` and `Sca=0`;
- each transaction's `Trt` references the other transaction;
- the references are reciprocal;
- amounts are exact opposites;
- each payment method belongs to its own account and supports its amount direction;
- each side may retain its own value date, payment content, marked state and reconciliation information.

Supported typed operations:

```json
{"type":"createTransfer", "accountId":"1", "targetAccountId":"2", "date":"07/16/2026", "amount":"-40.00", "paymentMethodId":"3", "targetPaymentMethodId":"7"}
```

```json
{"type":"updateTransfer", "transactionId":"3", "changes":{"amount":"-45.00"}}
```

```json
{"type":"deleteTransfer", "transactionId":"3"}
```

The operation may target either side of the reciprocal pair. Updating the destination account removes the old counterpart and creates a new reciprocal counterpart while preserving the Grisbi fields that remain meaningful.

## Reconciled transfer safeguards

Grisbi's `Ma` field defines the visible transaction state:

- `0`: normal / unchecked;
- `1`: checked;
- `2`: telepointed;
- `3`: reconciled.

`Re` is not sufficient to decide whether a transaction is currently reconciled, because Grisbi may retain an old reconciliation number after the transaction is moved back to another state. Phase 6 therefore treats `Ma=3` as the authoritative reconciled state.

Updating, deleting or converting a transfer when either side has `Ma=3` returns:

```text
confirmation-required
```

The protocol error includes the reason and affected transaction IDs. The current editor asks the user for explicit confirmation and retries the same ETag-protected atomic operation with `allowReconciled: true`.

## Damaged historical transfer links

The following conditions are compatibility warnings rather than fatal document errors:

- a `Trt` target is missing;
- a `Trt` relationship is not reciprocal.

The account can still open. The snapshot marks the affected transaction as a broken transfer, and the normal editor keeps the row read-only. Unrelated valid transactions and quick checked/unchecked changes remain usable.

Structural XML errors, duplicate IDs, invalid amounts, missing accounts/currencies and other unsafe references remain fatal.

## Normal transaction and transfer conversion

### Normal to transfer

```json
{
  "type":"convertTransactionToTransfer",
  "transactionId":"1",
  "targetAccountId":"2",
  "paymentMethodId":"3",
  "targetPaymentMethodId":"7"
}
```

The existing transaction ID is preserved. Its category/subcategory are cleared, a counterpart is allocated server-side, and reciprocal `Trt` links are added.

### Transfer to normal

```json
{
  "type":"convertTransferToTransaction",
  "transactionId":"1",
  "categoryId":"1",
  "subcategoryId":"7"
}
```

The selected transaction ID is preserved, its `Trt` is cleared, the counterpart is deleted, and the selected normal category is applied.

The current compact grid requires unrelated field edits to be saved before conversion. The future responsive editor can present conversion as a dedicated form without changing the backend contract.

## Fast checked/unchecked mutation

Bank verification does not require opening every transaction editor. The client groups all direct checkbox changes into one operation:

```json
{
  "type":"setTransactionMarks",
  "marks":[["1",1],["2",0],["3",1]]
}
```

Rules:

- each entry is `[transactionId, 0|1]`;
- duplicate IDs are rejected;
- states `2` and `3` cannot be changed by this shortcut;
- normal, transfer, breakdown and split-child rows can be checked/unchecked when their current state is `0` or `1`;
- the operation supports up to 1000 entries;
- the normal expected workflow is roughly 50 entries or fewer.

When a transaction has no other changes, the lossless writer patches only the exact value of its `Ma` attribute. It does not serialize the surrounding transaction. A test with 64 rows verifies that every byte outside the changed `Ma` values remains identical.

If a transaction also has a normal structural edit in the same batch, the session merges the new mark into the one replacement record instead of producing overlapping patches.

## Grisbi display preferences

The compact snapshot now exposes, without repeating them per transaction:

- account `Lines_per_transaction`;
- General `Two_lines_showed`;
- General `Three_lines_showed`;
- General `Transactions_view`;
- General `Transaction_column_width`;
- account `Sorting_kind_column`.

The Grisbi 1.2.2 fixture currently requests three lines per transaction. These values are intentionally only transported and decoded in Phase 6. The exact responsive desktop/mobile presentation will be decided before the UI phase.

## Fixtures

Two fixtures are retained:

- `grisbi-1.2.2-basic.gsb`: the original deterministic fixture used by Phases 0–5 for byte-level compatibility assertions;
- `grisbi-1.2.2-real.gsb`: the real file produced by Grisbi 1.2.2, used for Phase 6 transfer, preference and payment compatibility tests.

This separation prevents realistic preference/category data from invalidating earlier surgical-write tests.

## Performance contract

Phase 6 does not impose an unrealistic latency target for unusually large checked/unchecked batches. It guarantees instead that:

- the request is parsed as one mutation batch;
- the GSB file is decoded and parsed once before mutation;
- the file is rendered and envelope-encoded once after mutation;
- a mark-only row patches only `Ma`;
- the existing compact snapshot and virtual scrolling remain unchanged;
- the file is still written once through the ETag-protected Nextcloud service.
