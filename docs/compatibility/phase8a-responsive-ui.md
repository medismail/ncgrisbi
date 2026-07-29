# Phase 8A — responsive batch transaction UI

Phase 8A replaces the permanent editable grid with a responsive, virtualized transaction list and one active transaction editor. It keeps the Phase 6 compact snapshot, lossless mutation engine, ETag concurrency and one-write batch save.

## Approved scope

Implemented feature groups:

- UI-01 through UI-06: shared desktop/mobile state, virtual scrolling, text rows, one active editor, Grisbi line preference and manual compact/detailed switch.
- UI-11 through UI-17: desktop side panel, mobile full-screen editor, common/advanced field separation, dedicated transfer editor, local save/cancel and close warning.
- UI-21 through UI-28: persistent add controls, mobile floating add, today/default payment/focus behavior, missing reference creation, save-and-add-next and multiple pending new transactions.
- UI-30 through UI-37: reusable local autocomplete with keyboard/touch operation, normalized prefix/substring matching, recents, retained selected IDs and explicit create actions.
- UI-41 through UI-45: party history completion, current-account preference inherited from the snapshot, non-destructive filling, highlighted completed fields and undo.
- UI-50 through UI-57: direct checked/unchecked state, local batching, pending counts, locked telepointed/reconciled states and bank-status filters.
- UI-61 through UI-69: transfer category, destination account, source/counterpart payment methods, opposite amount, reciprocal-change notice, conversions, reconciled confirmation and broken-transfer read-only state.

## Batch editing contract

The transaction editor has two different save levels:

1. **Save draft** applies the open editor to local browser state only.
2. **Save all to file** validates every pending new, changed, deleted and checked transaction and sends one mutation request.

Users may therefore:

- create several new transactions;
- modify several existing transactions;
- check or uncheck many transactions;
- close and reopen the editor;
- perform one final GSB file write.

`Save draft & add another` applies the current draft locally and immediately opens a new transaction editor. This is the optimized workflow for entering a statement containing many transactions.

An open valid editor is included when the user presses `Save all to file`, even if `Save draft` was not pressed separately.

## Responsive list

The fields always visible on desktop and mobile are:

- date;
- party;
- amount;
- marked state;
- status.

Desktop also shows category/subcategory. Detailed mode adds payment method, counterpart method, note and bank reference. On mobile, detailed data occupies a second line and the editor opens full-screen without horizontal page scrolling.

The initial row mode follows Grisbi `Lines_per_transaction`, `Two_lines_showed` and `Three_lines_showed`. The user can switch compact/detailed mode for the current session. Persisting that switch to the GSB file is deferred.

## Autocomplete identity

Visible names remain user-friendly, but each selected suggestion stores its exact Grisbi ID in the local draft. The responsive planner narrows duplicate-name resolution to that selected ID before delegating to the existing typed operation planner. Free text remains available for creating missing parties, categories and subcategories.

Autocomplete is entirely local. No request is sent for each keystroke.

## Party completion

Selecting a party may complete only currently empty/default fields. Completed fields are highlighted and can be reverted with one Undo action. The exact party/category/subcategory/payment IDs from the compact snapshot are retained where available.

## Performance invariants

- Compact snapshot format retained.
- `DynamicScroller` retained.
- Transaction rows are primarily text, not permanent form controls.
- Only one full editor is mounted.
- Multiple local drafts are supported.
- Quick marks remain one `setTransactionMarks` operation.
- No per-field or per-transaction automatic file write.
- One Phase 6 mutation session and one Nextcloud file write per explicit global save.

## Deferred autosave

Autosave is not enabled in Phase 8A. A future preference may save pending changes automatically when switching accounts, but it must remain optional and must use the same validation, ETag and confirmation behavior as explicit `Save all to file`.
