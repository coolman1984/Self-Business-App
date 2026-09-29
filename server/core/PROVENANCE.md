# Provenance of the harvested engine

Source: `coolman1984/Mr.Ayman-HR` (BAMS) commit `5f5b3ce063ea1446c6daaa3b5b3477d2157d810c`, version 2.4.0, read-only.
Owner of both projects: Mohamed Fawzy (the code is his own, so re-use is allowed).
Rule: every change to a harvested file is listed here with its reason. A test (`tests/test_layers.py`) checks that every
harvested module is mentioned in this file and that the core contains no business vocabulary.

## Harvested files

| File | What changed and why |
|---|---|
| `ed25519.py`, `tlscert.py`, `node.py`, `nodectl.py`, `xlsx.py` | prefix rename only (`BAMS`→`SBO`, `bams`→`sbo`). `nodectl.py`: rebuild no longer copies the old in-database transaction table. |
| `journal.py` | rename; **envelope v2** (ADR-008): the signed body carries `ops_hash`, the operations travel (`o`) and are stored beside it, so an authority-signed **erase order** (`kind: erase`, priority 4) can blank personal values in the stored history and the audit rows without breaking hash chains or signatures. `erased` table, `_redact_incoming`, `reapply_erasures`, `redacted` column. Audit column `area_id`→`scope_id`, op key `a`→`sc`, query args `area(s)`→`scope(s)`. |
| `replica.py` | rename; resolver `min`; **write-once records** (`immutable` entities: the earliest write wins whatever the arrival order, later writes are remembered in `sync_dropped` and flagged `edited-after-issue`); `erase` kind handling (removes stored values, writes null at the highest priority); `touched` set for the derived search index. |
| `sync.py` | rename only. |
| `backup.py` | rename; file-name slicing now uses `PREFIX` (lesson from Trip Orders: a blind rename shortened the prefix and broke position slices). |
| `system.py` | rename; the BAMS v1→journal upgrade path (`_upgrade`, `_boot_*`) removed: this product starts with the journal on day one; erasures are re-applied at every start. |
| `store.py` | rename; no break-area entities: entities come from `registry.py`; `state()`, survey rules, `export_sheets` domain sheets, in-database legacy logs removed; generic `get`, `sync_schema`, scope lookup, duplicate rules and file references from the registry; `erase()`; refuses edits of write-once records and of erased fields; restore skips erased fields; `after_fold` hooks. |
| `auth.py` | rename; permissions and ready-made profiles come from `permissions.py`; users get `data_scope` (`all`/`scopes`/`own`) and `scopes` instead of break-area lists; **scrypt** password hashes (N=2^17, r=8, p=1) with PBKDF2 hashes still verified and upgraded at the next login on the administrator PC; password-proof key derivation uses scrypt (`SBO-ACCOUNT2`); `verify_current_password`. |
| `version.py` | rewritten (product, version, owner). |

## Written here (not harvested)

`registry.py` (entity registry), `permissions.py` (permission registry), `query.py` (filtered, scoped, masked, paginated reads),
`search.py` + `textnorm.py` (derived Arabic-aware search index), `httpd.py` (router, from BAMS `app.py` made domain-free),
`bootstrap.py` (registration hook). Entry points: `server/app.py`, `server/sbo_main.py`.

## Not harvested (rewritten later)

BAMS `js/*` (UI, English only, one file) — replaced by the new UI in Phase 2. BAMS installer `bams.iss` — replaced by `installer/sbo.iss`
(no old-data import).
