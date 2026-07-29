# Target backend architecture

## Compatibility boundary

The current target remains unchanged:

- desktop application target: Grisbi 1.2.2;
- writable GSB file format: 1.2.1;
- GSB 2.3.2 is intentionally rejected.

This architecture is ready for additional format profiles, but it does not add
or imply support for another version.

## Runtime path

```text
Nextcloud controller/service
        |
        v
GrisbiProcess.php
        | framed binary protocol; password on descriptor 3
        v
lib/bin/ncgrisbi_protocol.py
        |
        v
ncgrisbi.worker
        +-- framing.py
        +-- envelope.py
        +-- parser.py
        +-- formats/
        |     +-- base.py
        |     +-- gsb_121.py
        +-- validator.py
        +-- read.py
        +-- snapshot.py -> _snapshot_core.py
        +-- mutation.py -> _mutation_core.py
        +-- writer.py
```

All production commands use this path. There are no alternate protocol workers,
legacy command-line readers or parallel mutation engines.

## Final package files

Public responsibility modules:

- `envelope.py` — compression and encryption envelope handling;
- `errors.py` — backend exception taxonomy;
- `formats/` — explicit format registry and isolated version profiles;
- `framing.py` — binary PHP/Python transport and descriptor-3 password input;
- `model.py` — immutable parsed document and exact byte spans;
- `mutation.py` — canonical batch mutation API and profile-owned creation;
- `parser.py` — one lossless XML parse and top-level span scan;
- `read.py` — JSON read models with one-pass request indexing;
- `snapshot.py` — canonical compact editor snapshot API;
- `validator.py` — semantic and profile-schema validation;
- `worker.py` — command dispatch only;
- `writer.py` — byte-preserving patch rendering.

Private implementation cores:

- `_mutation_core.py` — proven transfer, conflict, mark and render algorithms;
- `_snapshot_core.py` — compact snapshot wire construction.

The private cores are separated because they are large, performance-sensitive
algorithms. They are not alternate APIs and are never imported by PHP or the
entrypoint directly.

## Format profile boundary

`formats/base.py` defines `FormatProfile`. A profile owns every rule that may
vary by `General.File_version`:

- canonical record attribute order;
- required attributes used by validation;
- section ordering used for insertion;
- defaults for newly created records;
- record serialization;
- declared read/write support level;
- operation capabilities.

`formats/gsb_121.py` contains all 1.2.1-specific schema and defaults. The registry
in `formats/__init__.py` is the only place that exposes supported versions.
Parser, validator, mutation and writer code do not contain a second-version
branch.

A future profile must be added as a separate file and registered explicitly.
Until that happens, a file declaring `2.3.2` raises
`UnsupportedFileVersionError`.

## Performance model

The backend keeps the following hot-path properties:

- one Python process per framed request;
- one envelope decode and one XML parse per input request;
- one batch mutation session for all submitted operations;
- one final XML parse for semantic verification after a changed mutation;
- no re-encryption, recompression or serialization for a no-op;
- `Ma`-only changes patch only the attribute value;
- read requests build lookup maps in one direct-child pass;
- transaction list totals are calculated in the same loop that builds rows;
- no subprocess shell and no password in command-line arguments.

The read index is request-local. This avoids persistent mutable caches and keeps
memory proportional to one open document while eliminating repeated XPath-style
lookups and duplicate map construction.

## Unified worker commands

The framed worker exposes:

- `inspectEnvelope`;
- `documentInfo`;
- `listAccounts`;
- `listParties`;
- `listCategories`;
- `listTransactions`;
- `accountSnapshot`;
- `mutate`.

`inspectEnvelope` does not decrypt or parse the file. Other read commands parse
and validate once before constructing their response. `mutate` applies the whole
operation array atomically and returns one rendered payload.

## Removed files

The following backend generations and compatibility layers are deleted:

- `lib/bin/grisbi.py`;
- `lib/bin/ncgrisbi_legacy.py`;
- `compat_engine.py`;
- `completion_history.py`;
- `index.py`;
- `mutation_engine.py`;
- `mutations.py`;
- `phase4_protocol.py`;
- `phase5_protocol.py`;
- `phase6_engine.py`;
- `protocol.py`;
- `read_service.py`;
- `resolution.py`;
- `serializer_121.py`;
- `snapshot_service.py`.

No production module or public package export refers to them.

## Preserved safety guarantees

- a no-op returns the original bytes exactly;
- unknown attributes and unsupported sections are preserved;
- the declared file format cannot change during rendering;
- gzip and encryption state is retained;
- passwords use descriptor 3;
- PHP verifies request IDs and response SHA-256 values;
- shared locks protect snapshots;
- exclusive locks and ETags protect writes;
- transfer pairs, reconciled-state confirmation and quick-mark restrictions are
  preserved.

## Tests

The compatibility suite now checks:

- the 1.2.1 profile and creation defaults;
- profile-aware validation and lossless writing;
- profile-owned record creation through `mutation.py`;
- current-account completion precedence;
- all unified read commands;
- password-free envelope inspection;
- explicit rejection of GSB 2.3.2;
- absence of every transitional module;
- canonical runtime imports;
- one-pass read-model source contracts.

## Adding another version later

The safe sequence remains:

1. collect real files written by the exact target Grisbi desktop version;
2. add a new isolated profile under `formats/` in read-only mode;
3. add parser, validator and snapshot fixtures;
4. validate desktop open-save-reopen behaviour;
5. enable one mutation capability at a time only after exact round-trip tests.
