# Grisbi 1.2.2 / GSB 1.2.1 compatibility contract

## Status

This document defines the compatibility target for NCGrisbi before the write path is redesigned.

- Target desktop application: **Grisbi 1.2.2**
- Target file compatibility marker: **1.2.1**
- Upstream reference: `grisbi/grisbi`, tag `upstream_version_1_2_2`
- NCGrisbi scope: preserve the complete document while supporting selected finance operations

Grisbi 1.2.2 identifies the minimum compatible file format as `1.2.1`. The application version and file version must therefore not be treated as the same value.

## Meaning of compatibility

For this project, 100% compatibility means that:

1. NCGrisbi can read a file produced by Grisbi 1.2.2.
2. Grisbi 1.2.2 can read a file modified by NCGrisbi.
3. Unsupported sections and attributes are preserved.
4. Updating one exposed field does not reset unrelated Grisbi metadata.
5. Newly created records use Grisbi 1.2.2 names, identifiers, defaults, escaping and record layout.
6. A no-op operation returns the original bytes unchanged.
7. Invalid or conflicting writes never replace the original Nextcloud file.

Compatibility does not require NCGrisbi to expose every Grisbi feature in the user interface.

## Phase 0 scope

Phase 0 establishes the executable contract only. It intentionally does not replace the current writer.

Included in Phase 0:

- a documented format target;
- a canonical plain XML fixture;
- canonical expected transaction, party, category and subcategory records;
- section-order checks;
- attribute-order checks;
- reference-integrity checks;
- a baseline test against the current parser;
- an expected-failure test demonstrating that the current whole-document serializer is not byte preserving;
- a GitHub Actions job for the compatibility contract.

The no-op preservation test is marked `xfail(strict=True)` until Phase 1 introduces a lossless patch writer. It must become a normal passing test before the new write engine is considered complete.

## File envelope

The logical XML document may be stored using these envelopes:

1. plain XML;
2. gzip-compressed XML;
3. Grisbi v2 encrypted XML;
4. gzip-compressed encrypted content.

Phase 0 includes a plain XML fixture. Binary envelope fixtures will be added with the envelope implementation in Phase 1 so their generation and verification can use the same deterministic codec tests.

## Top-level section ordering

The Grisbi 1.2.2 writer emits the main sections in this order:

1. `General`
2. colour and display data when present
3. `Print`
4. `Currency`
5. `Account`
6. `Payment`
7. `Transaction`
8. `Scheduled`
9. `Party`
10. `Category` and `Sub_category`
11. budget data
12. currency links
13. banks
14. financial years
15. archives
16. reconciliations
17. import rules
18. partial balances
19. forecast data
20. reports

The Phase 0 fixture contains only the sections needed for the first compatibility contract, but their relative order follows the upstream writer.

## Canonical transaction record

The attribute order for a Grisbi 1.2.2 transaction is:

```text
Ac Nb Id Dt Dv Cu Am Exb Exr Exf Pa Ca Sca Br No Pn Pc Ma Ar Au Re Fi Bu Sbu Vo Ba Trt Mo
```

Important meanings:

- `Ac`: account number;
- `Nb`: globally unique transaction number;
- `Id`: imported transaction identifier;
- `Dt`: transaction date;
- `Dv`: value date;
- `Cu`: currency number;
- `Am`: amount;
- `Pa`: party/payee number;
- `Ca`, `Sca`: category and subcategory numbers;
- `Br`: split-transaction flag;
- `Pn`, `Pc`: payment method and payment content;
- `Ma`: marked/reconciliation state;
- `Ar`: archive number;
- `Re`: reconciliation number;
- `Fi`: financial year;
- `Bu`, `Sbu`: budget and sub-budget;
- `Vo`: voucher;
- `Ba`: bank reference;
- `Trt`: contra-transaction number for a transfer;
- `Mo`: mother transaction number for a split.

A partial edit must preserve every attribute not explicitly changed.

## Canonical party record

```text
Nb Na Txt Search IgnCase UseRegex
```

A newly created party uses:

```text
new party number = maximum existing party number + 1
```

The initial default values are:

- `Txt="(null)"`
- `Search="(null)"`
- `IgnCase="0"`
- `UseRegex="0"`

Name matching must follow the desktop application's case-insensitive behaviour rather than silently creating duplicate parties.

## Canonical category records

Category attribute order:

```text
Nb Na Kd
```

Subcategory attribute order:

```text
Nbc Nb Na
```

Identifier rules:

- category number: maximum category number plus one;
- subcategory number: maximum subcategory number inside the selected parent category plus one.

Category type `Kd`:

- `0`: credit;
- `1`: debit;
- `2`: special category, including transfer/split semantics.

When a category is created from a normal transaction, its type is derived from the transaction amount.

## Identifier and reference invariants

Before a write is accepted:

- transaction numbers are unique across the document;
- transaction IDs are allocated by the server from the maximum existing positive number;
- every transaction account exists;
- every nonzero party exists;
- every nonzero category exists;
- every nonzero subcategory exists under the referenced category;
- every payment method belongs to the transaction account;
- every currency exists;
- every amount is a valid decimal;
- transfer links are reciprocal;
- split mother/child references are consistent.

Identifier allocation must occur inside the atomic server-side mutation, never in browser state.

## Preservation-sensitive fields

The fixture deliberately contains an existing transaction with values for:

- imported identifier;
- value date;
- marked state;
- reconciliation number;
- financial year;
- budget and sub-budget;
- voucher;
- bank reference.

These fields are the initial guard against the current behaviour of reconstructing edited transactions with defaults.

## Fixture provenance

`tests/compatibility/fixtures/grisbi-1.2.2-basic.gsb` is a synthetic canonical fixture derived from the serializers in:

- `upstream_version_1_2_2/src/gsb_file_save.c`
- `upstream_version_1_2_2/src/structures.h`
- the corresponding party, category and transaction data implementations.

It is synthetic so it contains no personal finance data and can exercise exact edge cases. A later fixture set may additionally include files manually generated and re-saved by an installed Grisbi 1.2.2 binary.

## Running the contract

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Expected Phase 0 result:

- all parser and contract checks pass;
- the no-op writer check is reported as one expected failure.

## Exit criteria for Phase 1

Phase 1 is not complete until:

1. the no-op test is no longer marked as expected failure;
2. no-op output is byte identical for every fixture;
3. one-record mutations alter only the intended byte ranges;
4. plain, gzip and encrypted envelopes round-trip correctly;
5. all unsupported records and attributes remain unchanged.
