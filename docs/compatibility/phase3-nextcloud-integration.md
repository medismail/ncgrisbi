# Phase 3: Nextcloud integration and concurrency control

Phase 3 connects the validated Phase 2 mutation engine to Nextcloud without
changing the Vue transaction editor yet. The old raw-attribute write endpoint is
disabled; later UI phases must use the typed mutation API.

## HTTP API

### `POST /apps/ncgrisbi/api/document`

Request body:

```json
{"filePath":"Documents/accounts.gsb"}
```

The response contains the file ID, current ETag, size, and detected envelope
flags. The client must retain the ETag and send it with its mutation request.
This POST endpoint uses the normal Nextcloud request token.

### `POST /apps/ncgrisbi/api/mutations`

Request body:

```json
{
  "filePath": "Documents/accounts.gsb",
  "baseEtag": "client-etag",
  "filePassword": "optional password",
  "operations": [
    {"type":"updateTransaction","transactionId":"10","changes":{"note":"Updated"}}
  ]
}
```

The endpoint requires Nextcloud CSRF validation. A successful response returns
the new ETag, output checksum, changed flag, and per-operation outcomes.

A stale `baseEtag` is rejected with HTTP 409 and the current ETag. Validation
errors are returned as HTTP 422. Locked files return HTTP 423. The old
`/api/savetransaction` endpoint returns HTTP 410 so an old client cannot bypass
partial-update preservation or optimistic concurrency.

## Application-level atomicity

The service performs the mutation in this order:

1. Resolve the file inside the authenticated user's folder.
2. Acquire an exclusive Nextcloud file lock.
3. Compare the locked file's current ETag with `baseEtag`.
4. Read the original bytes.
5. Run and fully validate the complete typed mutation batch in Python.
6. Recheck the ETag while the exclusive lock is still held.
7. Perform one `File::putContent()` call only when output bytes changed.
8. Return the refreshed ETag and release the lock in `finally`.

No file write occurs for malformed requests, invalid Grisbi data, wrong
passwords, failed mutation batches, or stale ETags. This is application-level
atomicity using Nextcloud's public file and locking APIs; the storage backend
retains responsibility for the crash semantics of its single write operation.

## PHP/Python binary protocol

The process boundary is binary safe and length-prefixed:

```text
4-byte big-endian JSON-header length
UTF-8 JSON header
raw GSB payload bytes
```

Both requests and responses use this format. Each header includes
`payloadLength`; successful responses additionally include SHA-256, mutation
outcomes, and a request ID echoed from PHP. JSON and diagnostic stderr can never
be confused with binary `.gsb` output.

The protocol supports these typed operations from Phase 2:

- `createParty`
- `createCategory`
- `createSubcategory`
- `createTransaction`
- `updateTransaction`
- `deleteTransaction`

Camel-case HTTP fields are strictly translated to the engine's typed fields.
Unknown operation fields are rejected rather than ignored.

## Password transport

Passwords are never placed in:

- the operating-system command line;
- environment variables;
- the framed JSON request;
- stderr or application logs.

PHP writes the password to inherited file descriptor 3 and closes it. The Phase
3 mutation worker reads that descriptor directly. Existing read-only commands
run through `ncgrisbi_legacy.py`, which also reads descriptor 3 and injects the
password only into the in-process Python argument list required by the old
reader.

## Process reliability

`GrisbiProcess` uses command arrays with shell bypass, handles partial pipe
writes, drains stdout and stderr concurrently with `stream_select`, verifies
process exit status, applies a timeout, validates response framing, checks the
request ID, and verifies the SHA-256 checksum before returning output to the
file service.

## Phase boundary

Phase 3 exposes the safe backend integration but does not migrate the existing
Vue editor. Party/category creation and normal transaction UX will consume this
API in the following phases. Legacy read endpoints remain temporarily available,
but their passwords now use descriptor 3.
