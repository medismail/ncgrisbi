# Phase A backend consolidation

## Status

Phase A keeps the supported compatibility target unchanged:

- desktop application target: Grisbi 1.2.2;
- writable GSB file format: 1.2.1;
- GSB 2.3.2 is not accepted yet.

The purpose of this phase is to make file-format support explicit and to reduce
the application to one active backend path before a second profile is added.

## Active runtime path

```text
Nextcloud controller/service
        |
        v
GrisbiProcess.php
        | framed binary protocol, password on descriptor 3
        v
lib/bin/ncgrisbi_protocol.py
        |
        v
ncgrisbi.worker
        +-- framing.py
        +-- parser.py -> formats.py -> GSB_121_PROFILE
        +-- read_service.py
        +-- snapshot_service.py
        +-- mutation_engine.py
                |
                v
            phase6_engine.py implementation base
        +-- validator.py
        +-- writer.py
```

All production reads and writes now pass through the same envelope decoder,
lossless parser, format profile, validator and response framing.

## Format profile boundary

`FormatProfile` owns every rule that may vary by `General.File_version`:

- canonical record attribute order;
- required attributes used by schema validation;
- section ordering used for insertion;
- defaults for newly created records;
- serializer behavior;
- declared read/write support level;
- operation capabilities.

`GsbDocument` carries the profile selected from its `File_version`. The parser,
validator, lossless writer and active mutation session consume that profile.
Adding a future format therefore requires a new profile rather than changing a
global version tuple and accidentally retaining 1.2.1 write rules.

## Unified commands

The framed worker exposes these commands:

- `inspectEnvelope`;
- `documentInfo`;
- `listAccounts`;
- `listParties`;
- `listCategories`;
- `listTransactions`;
- `accountSnapshot`;
- `mutate`.

`inspectEnvelope` does not decrypt the file and is safe for the password prompt
flow. Other commands parse and validate the document before returning data or
applying mutations.

## Mutation ownership

`mutation_engine.py` is the production mutation facade. Its `MutationSession`
extends the proven Phase 6 implementation but overrides all record-creation
paths so they start from the active format profile:

- explicit party creation;
- implicit party creation from a transaction;
- explicit category and subcategory creation;
- implicit category and subcategory creation from a transaction;
- normal transaction and transfer base records.

Existing-record validation, transfer pairing, conflict detection, marking and
lossless rendering remain shared with `phase6_engine.py` during the transition.
The production worker does not import the older mutation protocol or engines.

## Legacy removal and compatibility shims

Removed executable legacy files:

- `lib/bin/grisbi.py`;
- `lib/bin/ncgrisbi_legacy.py`.

The following modules remain temporarily because older tests or external imports
may still reference them, but they are not on the production runtime path:

- `protocol.py` — old typed mutation decoder, with framing retained separately
  in `framing.py`;
- `phase4_protocol.py`;
- `compat_engine.py`;
- `mutations.py`;
- `phase5_protocol.py` — now only a shim to `worker.py`;
- `completion_history.py` — now only a shim to `snapshot_service.py`.

They can be deleted in a later maintenance change after downstream import usage
has been checked. Keeping them out of the active dependency graph prevents fixes
from being applied to the wrong engine.

## Preserved guarantees

Phase A preserves the existing safety model:

- a no-op returns the original bytes;
- targeted marking can patch only the `Ma` value;
- unknown attributes and unsupported sections are preserved;
- file format version cannot change during rendering;
- gzip and encryption envelope state is retained;
- passwords are passed through descriptor 3, not command-line arguments;
- PHP verifies framed request IDs and response SHA-256 values;
- shared locks protect snapshots;
- exclusive locks and ETags protect writes.

## Tests

`tests/compatibility/test_phase_a_backend.py` checks:

- profile selection and creation defaults;
- profile-aware validation and writing;
- globally keyed payment methods;
- profile-owned record creation through the production mutation facade;
- current-account completion precedence;
- unified framed read commands;
- password-free envelope inspection;
- absence of the removed legacy scripts;
- isolation of the active worker from deprecated backend generations.

The PHP source contracts additionally verify that reads use framed commands and
that the production process no longer has an executable legacy-wrapper path.

## Next phase

The next compatibility phase should add real Grisbi 3.90.1 / GSB 2.3.2 fixtures
and a `GSB_232_PROFILE` in read-only mode. No 2.3.2 mutation capability should
be enabled until real desktop open-save-reopen round trips pass for that exact
operation class.
