# Phase 5: normal transaction CRUD

Phase 5 connects the Vue account editor to the typed, lossless mutation stack built in Phases 1–4. The browser no longer reconstructs raw Grisbi XML attributes and no longer calls the disabled `/api/savetransaction` endpoint.

## Typed account snapshot

The editor loads:

```text
POST /apps/ncgrisbi/api/editor/account/{accountId}
```

The response contains one ETag-consistent snapshot with:

- account and currency metadata;
- exact party, category, subcategory, and payment-method identifiers;
- normal transaction fields used by the editor;
- the real Grisbi bank-reference field, `Ba`;
- protection flags for records using `Br`, `Trt`, or `Mo`;
- account totals calculated with `Decimal` and the currency precision;
- the file ETag that must be supplied to the mutation endpoint.

The snapshot is produced by the compatibility engine, not the legacy ElementTree reader. The service holds the NCGrisbi application shared lock while reading and verifies that the file ETag is unchanged after Python has built the snapshot.

## Create

New rows are submitted as `createTransaction` operations. Existing parties, categories, subcategories, and payment methods are sent by ID. A newly typed party/category/subcategory is sent through the Phase 4 name-resolution fields with `createMissing: true`, so all missing records and the transaction are created atomically.

The client never allocates a Grisbi transaction ID.

## Update

Existing rows are converted to `updateTransaction` operations containing only changed fields. Hidden Grisbi metadata is therefore preserved by the Phase 2 partial-update engine.

Updates can select existing parties/categories/subcategories by name. Creating a new reference while updating an existing transaction is rejected in the editor; the user must first create it with a new transaction. This keeps update planning deterministic until a later server-side update-name resolver is added.

## Delete

Normal records are submitted as `deleteTransaction`. New unsaved rows are removed locally without producing an operation.

Transactions using any protected relationship field are read-only:

- `Br`: breakdown/split relationship;
- `Trt`: reciprocal transfer relationship;
- `Mo`: split-child mother relationship.

Those records cannot be updated or deleted by the normal transaction editor. Transfers and split transactions remain assigned to Phases 6 and 7.

## Concurrency

Every save sends the snapshot ETag as `baseEtag`. On HTTP 409:

- the local draft is preserved;
- no automatic retry occurs;
- saving is blocked;
- the user must explicitly reload the current file.

After a successful batch, the editor reloads a new server snapshot so generated IDs, newly created references, totals, and ETag all come from the saved file.

## Password and CSRF handling

The Vue client uses `@nextcloud/axios` and `generateUrl`, so Nextcloud's request token is included automatically. The editor snapshot endpoint intentionally does not use `NoCSRFRequired`, because its request body can contain the Grisbi password.

The password continues to travel from PHP to Python only through file descriptor 3.

## Protocol

The framed worker now supports two commands:

- `mutate`: Phase 4 name-aware typed mutations;
- `accountSnapshot`: read-only JSON snapshot generation.

A handled domain error is returned as a valid protocol frame with process exit status zero. This allows PHP to preserve stable protocol codes rather than replacing them with a generic process failure.

## Phase boundary

Phase 5 supports create, partial update, and delete for normal transactions only. Transfer creation/editing belongs to Phase 6. Split transaction editing belongs to Phase 7. Broader UX, localization, bulk tools, and advanced metadata editors remain later work.
