# Local-first and Multi-device Sync

Status: Phase 0. Decision: **reuse the BAMS engine** (journal + deterministic fold + pinned TLS sync), studied line by
line (`journal.py`, `replica.py`, `store.py`, `sync.py`, `DISTRIBUTED_SYNC_ARCHITECTURE.md`), with three evidence-based
extensions. The BAMS design document stays the deep reference; this file records what changes and why.

## 1. Non-negotiables (from the brief and BAMS)

- Every PC has its own complete SQLite database and works alone.
- Never share a database file over the network; never copy database files between PCs as sync.
- Sync = logical signed changesets; same fold on every PC → same data (deterministic convergence).
- History is never rolled back; restore = compensating change; deletes are durable.

## 2. Why keep the BAMS engine (comparison)

| Option | Result |
|---|---|
| BAMS journal + fold (stdlib) | ✅ proven (convergence property tests, multi-process tests, 2 independent reviews); business-aware merge (counters, rank, follow, delete-wins); authority signatures; offline login; attachments by hash |
| cr-sqlite | ❌ native extension per platform, early-stage, column LWW only (wrong for money and counters), no signatures/authority |
| PowerSync / ElectricSQL | ❌ need a central Postgres + service; not peer-to-peer; the owner PC would have to be always on |
| CouchDB/PouchDB | ❌ a server on every PC + data-layer rewrite |
| Raft (rqlite/dqlite) | ❌ quorum: with 2 of 3 PCs off nobody writes — the opposite of offline-first |
| Automerge/Yjs | ❌ document CRDTs; mismatch with relational rows and reports (maybe later for rich notes) |

## 3. Extensions (each with its reason)

| # | Extension | Evidence / reason |
|---|---|---|
| S1 | **Envelope v2**: ops stored beside the envelope, envelope carries `ops_hash`; signature/chain cover the envelope | legal erasure must remove personal values from history without breaking verification (SECURITY §5). Cheapest now: no legacy data. |
| S2 | **Registry-driven specs** (entities, resolvers, counters, duplicate detectors, lock-after rules) instead of the `ENTITIES` dict | modules register entities; BAMS `SPECS` is already the right shape |
| S3 | **Relay transport** (later phase): the same pull/push protocol through an internet relay for teams that are not on one LAN; changesets are signed end-to-end; encrypted end-to-end if AES is available (ADR-011) | a 2–4 person team often works from home; BAMS sync is LAN-only by design |
| S4 | New resolvers: `min` (earliest date wins), `lock-after:status=issued` (fields frozen once a document is issued; later concurrent edits → flag) | money snapshots (ARCHITECTURE §5.4) |
| S5 | Derived `index.db` rebuilt after fold (search, timeline, attention) | read performance; never replicated |

Kept exactly: HLC, version vectors, per-origin gapless `cseq`, causal delivery, `prev` hash chain, Ed25519 node and
authority signatures, deterministic refusals (`_check`), epochs and clone detection, schema number with "wait for
update", CAS attachments with resumable verified transfer, backup PC role for the authority key, alerts, sync log.

## 4. Merge rules for business data (conflict policy matrix)

| Entity | Concurrent insert | Same field concurrently | Delete vs edit | Special |
|---|---|---|---|---|
| parties, contact points | keep both + possible-duplicate flag (same normalised phone/email) | LWW, surfaced in "To decide" | delete wins, edit kept + flagged | merge = redirect (`merged_into`), never rewrite |
| opportunities, projects, tasks, tickets | keep both | `status` = `rank` (e.g. done beats doing), other fields LWW surfaced | delete wins, flagged | follower fields travel with their leader (`closed_at` follows `status`) |
| quotes/invoices (draft) | keep both | LWW surfaced | delete wins | |
| quotes/invoices (issued) | — | `lock-after:status=issued`: snapshot fields never change; concurrent edits flagged "edited after issue" | void instead of delete | number assigned by the issuing PC's series |
| payments, allocations, time entries (approved), attendance marks, ticket events, activities | keep all (events) | — | delete only via reversal event | possible-duplicate payment flag (party+amount+day+method) |
| revision rounds used, licence seats used | **counter** (deltas add up) | — | — | negative/over-limit flagged |
| settings, brand | per key LWW surfaced | | | |
| users, profiles, devices | authority only (BAMS) | admin > own-password | | |
| automation runs, outbox | runner PC only; deterministic ids | | | idempotency key per external effect |
| snooze/dismiss of attention items | per user LWW | | | |

"To decide" screen (BAMS pattern, renamed): conflicts, possible duplicates, edited-after-issue, delete-vs-edit,
negative counters — the same list on every PC.

## 5. Operating modes

| Mode | Who | How |
|---|---|---|
| Solo | one person, one PC | full engine runs; sync idle; backups mandatory |
| Solo + laptop | same person, 2 PCs | both join the same business; LAN or relay |
| Small team on LAN | 2–4 people in one office | BAMS model: every PC complete, admin PC holds the authority key, backup admin PC optional |
| Small team remote | team at home/offices | relay transport (later), same guarantees |
| Browser-only colleague | assistant on a phone/tablet in the office | opens the owner's PC address; works only while that PC is on |

## 6. Tests (kept + new)

Kept from BAMS: unit (crypto vectors, canonical JSON, HLC, fold properties), randomised multi-replica convergence
with fixed seeds (partitions, duplicate/reordered/truncated delivery), multi-process harness with TCP proxy (unplug a
PC), rebuild-from-journal identity. New: issued-document lock under concurrency, payment duplicate flag, merge by
redirect under concurrency, erase order across 3 PCs (chains verify, values gone everywhere, backup restore
re-applies), automation double-runner produces one result, module disabled on one PC while another writes its data.
