# Phase 1: lossless GSB 1.2.1 core

Phase 1 introduces the compatibility engine used by later mutation and
Nextcloud-integration phases. It does not replace the current application API
or transaction workflow yet.

## Guarantees implemented

- Plain, gzip, Grisbi encryption v2, and gzip-wrapped encryption v2 envelopes
  are detected in the same order as Grisbi 1.2.2.
- A document with no requested mutation is returned as the exact original byte
  sequence, including its original compression/encryption envelope.
- Direct children of `<Grisbi>` are mapped to exact byte spans by a quote-aware
  scanner. XML parsing remains responsible for semantic validation.
- Record replacement changes only the selected element span.
- Record insertion uses the Grisbi 1.2.2 save-section order and preserves the
  surrounding bytes, indentation, and newline convention.
- Transaction, party, category, and subcategory serializers use the canonical
  GSB 1.2.1 attribute order and XML escaping.
- Overlapping byte patches are rejected before output is generated.
- Patched output is reparsed and checked for the original root and file version.

## Modules

- `envelope.py`: compression/encryption detection, decode, and encode.
- `parser.py`: XML validation and exact top-level byte-span discovery.
- `model.py`: immutable document and span metadata.
- `serializer_121.py`: canonical supported-record serialization.
- `writer.py`: surgical replacement, deletion, insertion, and envelope output.
- `errors.py`: explicit compatibility-engine exceptions.

## Phase boundary

The legacy `grisbi.py` command path continues to exist unchanged. Routing the
application's create/update/delete operations through this engine belongs to
the mutation and integration phases. Keeping this boundary prevents an
unfinished mutation protocol from being coupled to the new writer.
