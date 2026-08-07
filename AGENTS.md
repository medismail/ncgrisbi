# AGENTS.md

Nextcloud app (`ncgrisbi`) for viewing/editing Grisbi account files (`.gsb`). Vue 3 frontend + PHP Nextcloud backend that shells out to a Python worker over a framed binary protocol.

## Repo layout

- `src/` — Vue 3 frontend (entry `src/main.js`). Built two ways: full app via `vue-cli-service` (`vue.config.js`), separate viewer bundle via `webpack.js` (`src/viewer.js`).
- `lib/` — PHP backend (`Controller/`, `Service/`, `Storage/`, `Migration/`, `Grisbi/`) plus `lib/bin/` Python worker.
- `lib/bin/ncgrisbi/` — the real backend: `worker.py` (entry), `envelope.py` (crypto/compression), `parser.py`, `read.py`, `snapshot.py`→`_snapshot_core.py`, `mutation.py`→`_mutation_core.py`, `writer.py`, `validator.py`, `formats/` (version profiles).
- `lib/bin/ncgrisbi_protocol.py` — thin shim that calls `ncgrisbi.worker.main`; this is the script PHP spawns.
- `appinfo/` — Nextcloud app metadata (`info.xml`), `routes.php`.
- `tests/compatibility/` — Python pytest suite (GSB format contract; the `pytest.ini` default `testpaths`).
- `tests/php/` — PHP contract tests run directly with `php <file>` (no phpunit).
- `tests/frontend/` — Node `.mjs` tests run with `node <file>` (no test runner).
- `dist/`, `js/`, `css/` — build outputs (gitignored, regenerated).

## Architecture: the framed protocol path

All production backend commands follow one path:

```
Nextcloud Controller/Service -> GrisbiProcess.php --(framed binary protocol, password on fd 3)--> lib/bin/ncgrisbi_protocol.py -> ncgrisbi.worker
```

- `GrisbiProcess.php` spawns `python3 lib/bin/ncgrisbi_protocol.py` and speaks the framing in `lib/bin/ncgrisbi/framing.py`.
- Password is passed via file descriptor 3, not argv or stdin. Do not add alternate protocol workers or legacy command-line readers.
- Supported write targets: GSB `1.2.1` (Grisbi 1.2.2) and GSB `2.0.0` (Grisbi 3.0.4). GSB 2.3.2 and other unlisted versions are intentionally rejected. Profiles live in `lib/bin/ncgrisbi/formats/`. See `docs/backend-architecture.md`.

## Development commands

Node 22 / npm 9 required (`package.json` engines).

| Task | Command |
| --- | --- |
| Install deps | `npm install` |
| Dev server (port 8081, proxies `/api` to `http://localhost/nextcloud` → `/index.php/apps/ncgrisbi/api`) | `npm run dev` |
| Build app | `npm run build` |
| Build standalone viewer bundle | `npm run buildviewer` |
| Watch build | `npm run watch` |
| Lint (JS/Vue) | `npm run lint` / `npm run lint:fix` |
| Stylelint | `npm run stylelint` / `npm run stylelint:fix` |

`make build` runs `npm run build && npm run buildviewer` after `npm install`. `make dist` copies `dist/js` → `js/` and `dist/css` → `css/` (the dirs Nextcloud serves). `make appstore` produces the appstore tarball excluding dev/source paths.

## Tests

No `npm test` / no JS test runner. Tests are invoked explicitly per language.

Python (GSB compatibility contract):
```
python -m pytest                      # uses pytest.ini -> tests/compatibility
python -m pytest tests/compatibility/test_gsb_121_contract.py   # single file
python -m pytest tests/compatibility/test_noop_preservation.py::test_name   # single test
pip install -r requirements-dev.txt   # pytest + pycryptodomex
```
Backend modules are precompiled in CI via `python -m compileall -q lib/bin/ncgrisbi lib/bin/ncgrisbi_protocol.py lib/bin/gsb_decode.py`. `tests/compatibility/fixtures/` holds synthetic `.gsb` fixtures; `expected/` has canonical records. Synthetic data, no real financial info.

PHP (run each file directly with the php interpreter, not phpunit):
```
php tests/php/test_phase3_process.php
php tests/php/test_phase3_document_service.php
# or loop: for f in tests/php/test_*.php; do php "$f"; done
```

Frontend (Node, no runner):
```
node tests/frontend/test_phase5_editor.mjs
node tests/frontend/test_phase8a_ui.mjs
# also: test_phase8a_completion / _ordering / _search
```
CI additionally `node --check`s key `src/domain/*.mjs`, `src/services/gsbApi.js`, and `src/store.js`.

## Lint order before committing

CI does not run a single combined job. Mirror the `gsb-compatibility.yml` gate:
1. `npm run lint` (ESLint, `plugin:vue/vue3-recommended`)
2. PHP syntax: `find lib appinfo tests/php -name '*.php' -print0 | xargs -0 -n1 php -l`
3. `node --check` on the modules listed above
4. Python compatibility: `python -m pytest`
5. PHP contract tests + frontend `.mjs` tests as in the workflow

ESLint: `.eslintrc.js` extends `eslint:recommended` + `plugin:vue/vue3-recommended`; `appVersion` is a known global; jsdoc rules off.

## Gotchas

- `vue.config.js` sets `filenameHashing: false` and `publicPath: './'`; `indexPath` is `templates/main.php`. The app entry is `./src/main.js`; the viewer is a separate webpack entry in `webpack.js` (`src/viewer.js` → `dist/js/viewer.js`).
- `Makefile` derives the version from `appinfo/info.xml` (`<version>` tag). Bump version there, not in `package.json`, for appstore packaging.
- `.gitignore` ignores `build`, `js`, `css`, `dist`, `node_modules`, and also `.eslintrc.js` and `package-lock.json` — these last two are tracked-by-exception (they exist despite the ignore).
- `pytest.ini` has `xfail_strict = true`: an `xfail` that unexpectedly passes fails the run. Do not sprinkle `xfail` loosely.
- Two distinct CI workflows: `backend-compatibility.yml` (path-filtered to lib/tests changes) and `gsb-compatibility.yml` (the full contract gate on `main` / `agent/**` branches and PRs). Be aware both can run on a PR.
- `GrisbiProcess::createForTesting` keeps the legacy wrapper arg for test compat but ignores it — production always uses the framed worker and fd 3 for passwords.
