# Phase 5: optimized Grisbi-compatible transaction editor

Phase 5 connects the Vue editor to typed lossless mutations while retaining the behaviour users depend on in Grisbi 1.2.2: compact account loading, account/sign-aware payment choices, reciprocal transfers, and payee completion.

## Compact account snapshot

`POST /apps/ncgrisbi/api/editor/account/{accountId}` returns an ETag-consistent version-2 wire snapshot. The wire shape uses short keys and positional arrays and does not repeat party, category, subcategory, payment, or account names in every transaction. The browser decodes it into descriptive objects in `snapshotWire.mjs`.

The transaction list uses `DynamicScroller`; only visible rows create DOM inputs. This fixes both sources of the original Phase 5 regression: oversized JSON and rendering every transaction at once.

A 1,001-transaction compatibility benchmark produces 124,467 bytes with the compact shape versus 456,690 bytes with the original Phase 5 verbose shape: 27.3% of the previous payload.

## Payment compatibility

Grisbi payment numbers are global identifiers. The `Account` field is a property used by the form to filter choices. Existing files are therefore accepted when a transaction references any globally existing payment number, even if historical data does not match the payment account.

For newly created or explicitly changed data, the editor follows Grisbi's form behaviour:

- the payment belongs to the selected account;
- a negative amount accepts debit (`Sign=1`) or neutral (`Sign=0`);
- a positive amount accepts credit (`Sign=2`) or neutral (`Sign=0`);
- account `Default_debit_method` and `Default_credit_method` are used when available.

An unrelated edit, such as changing a note, does not reject a historical payment reference that Grisbi itself can open.

## Transfers

Selecting `Transfer` as the category and an account as the destination creates two transactions in one atomic mutation:

- source and counterpart use `Ca=0`, `Sca=0`;
- amounts are exact opposites;
- each `Trt` points to the other transaction;
- each side uses a payment method valid for its account and amount direction.

Editing a transfer updates both records. Counterpart-specific value date, marked/reconciled state, and payment content are preserved unless explicitly changed, matching Grisbi's transfer update behaviour. Changing the destination removes the old counterpart and creates a new reciprocal counterpart. Deleting either visible side deletes the pair.

Same-currency reciprocal transfers are editable. Cross-currency transfers, breakdown mothers (`Br`), split children (`Mo`), and malformed transfer links remain read-only until their exact exchange or breakdown semantics are implemented.

## Payee completion

The snapshot includes one compact completion hint per payee. Selection prefers the most recent transaction in the current account, then another account, and ignores split children. A payment from another account is mapped by name and sign to a compatible payment in the current account.

When an exact payee is selected, the editor fills only fields that are still empty or at their initial zero value: amount, category/subcategory or transfer destination, payment method, note, payment reference, voucher, and bank reference. Existing user input is never overwritten.

## Concurrency and security

All saves still use the snapshot ETag as `baseEtag`. HTTP 409 preserves the local draft and requires an explicit reload. The snapshot uses the application shared lock; mutation uses the exclusive application lock and one final Nextcloud write. CSRF validation remains enabled, and the Grisbi password reaches Python only through file descriptor 3.

## Protocol operations

The Phase 5 worker supports normal Phase 4 operations plus:

- `createTransfer`;
- `updateTransfer`;
- `deleteTransfer`;
- `accountSnapshot` version 2.

The frontend never constructs raw Grisbi attributes and never allocates transaction identifiers.
