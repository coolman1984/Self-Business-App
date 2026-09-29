# Security and Privacy

Security is designed into the core (BAMS model), not added at the end. Status: Phase 0.

## 1. Assets

Client personal data · money records · business documents and files · user accounts · node and authority keys ·
backups (contain everything, incl. password hashes) · the journal (history).

## 2. Threat model (summary)

| Threat | Control |
|---|---|
| Unknown PC on the LAN joins or reads data | enrolment + pinned TLS certificates; revocation; (open-join "easy mode" only as an explicit setting) |
| Sniffing / MITM between PCs | TLS 1.3, pinned self-signed certificates (BAMS) |
| A normal user or PC forges admin/permission changes | authority-key signatures on `admin` changesets, verified on every PC |
| A PC changes someone else's password | password proof (BAMS: signature from a key derived from the old password) |
| UI-only permission bypass (calling the API directly) | every route checks permission + data scope + money visibility on the server; serializer strips fields |
| Brute force login | lockout (5 → 15 min), per-IP failure limiter, 64 kB pre-auth body limit (BAMS) |
| Session theft | random 256-bit tokens, only hashes stored, HttpOnly + SameSite=Strict cookies, idle timeout (30 min, not while typing) and absolute timeout (12 h), logout everywhere |
| CSRF | Origin check on every state-changing request (BAMS) |
| XSS | every value escaped (`esc`) by the UI kit; no `innerHTML` with data; strict CSP header; uploaded files served with `Content-Disposition` and sniffing disabled |
| Malicious upload | extension + magic-byte allowlist, size limit, content-addressed storage, never executed, never served from the static path |
| Tampering with history | hash chain + signatures, periodic verification, copies on every PC |
| Stolen backup | backups contain hashes and personal data → stored only on local disks (no network folders); encryption with a passphrase (AES-GCM if `cryptography` accepted, else BAMS sealed format) — owner question Q2 |
| Secrets in logs | never log passwords, tokens, link tokens, keys, licence keys (tested by a log-scanner test) |
| Portal exposure | office PC never reachable from the internet; the gateway holds only client-scoped minimal snapshots, expiring links, per-client tokens hashed |
| AI misuse | AI never executes money, delete or send actions without an explicit rule + human approval; prompts never include other clients' data |
| Supply chain | stdlib only (plus at most one approved dependency, pinned, with hash) |

## 3. Accounts and passwords

- Profiles (ready-made, editable): **Owner** (everything, locked), **Manager**, **Assistant**, **Accountant**,
  **Support**, **Viewer**. Built on BAMS tick-box permissions.
- Permission dimensions, all enforced on the server:
  1. **Pages/areas** (which screens).
  2. **Actions** per area: view / create / edit / delete (soft) / export / print.
  3. **Data scope**: all records · records of my clients/projects · only records assigned to me.
  4. **Money visibility**: sees amounts or not (serializer masks money fields; reports hidden).
  5. **Admin rights** (never on a personal link): users, backups, restore, settings, devices, import, legal erasure.
- Passwords: min length 10, blocklist of common passwords, no composition rules (NIST 800-63B style).
  Hash per ADR-011: scrypt (N=2^17, r=8, p=1, 16-byte salt) or Argon2id (if the dependency is accepted); existing
  PBKDF2-SHA256 600k hashes (engine compatibility) verified and re-hashed at next login. The password-proof key
  derivation follows the same KDF with its own domain string. A benchmark gate in Phase 1 keeps login < 1 s on the
  reference old laptop; if not, document the measured choice.
- Forced password change for temporary passwords; admin reset tool on the PC itself (BAMS `reset-admin`).

## 4. Data protection by design

- Soft delete for normal users; recycle bin; restore = new change.
- Every important change audited: who, when, which PC, old value, new value (journal audit view).
- Sensitive fields (national id, licence keys, notes marked private) are masked in lists and exports unless the
  permission `data.sensitive` is given; licence keys stored as hash + last 4 characters.

## 5. Legal erasure (separate, highly privileged)

"Never delete anything" is not lawful in every case (PDPL right to erasure, retention limits). Design (ADR-008):

1. Only a user with `privacy.erase` (off by default, even for managers) on the **authority PC**, with password
   re-entry and a typed confirmation.
2. An **erase order** is an admin-signed changeset containing only: target record ids and fields, reason code
   (e.g. `pdpl-request`, `retention-expired`), legal basis, request reference, actor. **No personal data.**
3. Every PC that folds the order: overwrites the fields in business rows with a redaction marker, **replaces the ops
   payload** of every journal changeset that carried those values (journal envelope v2 keeps `ops_hash` in the signed
   envelope, so chains and signatures still verify), scrubs audit before/after values, deletes the files from CAS if
   no other record uses them, rebuilds derived indexes.
4. Backups: the order is re-applied automatically when any backup is restored; backups older than the retention
   window are pruned; the erasure record says "backups expire on <date>".
5. The proof that remains: the erase order itself (ids, reason, date, actor, PCs that confirmed) — non-personal.
6. **Retention policies** (per entity, per role, e.g. leads not converted after 3 years) propose erase orders to the
   privileged user; nothing is erased automatically without that approval.
7. Money documents that must be kept by tax law are *anonymised* (party name replaced by "erased person #id")
   instead of removed; the legal-basis table decides per document type and country (tax connector provides it).

## 6. Security log

Logins, failures, lockouts, logouts, permission changes, exports, backups, restores, device joins/removals, erase
orders, automation approvals, portal link creation/revocation. Replicated, admin-only view (BAMS).

## 7. PDPL (Egypt Law 151/2020, Executive Regulations 2025) — product support

Consent records per contact and purpose · direct-marketing consent before any bulk message · data-subject export
(one click: all data about a person as a file) · erasure/anonymisation path (§5) · breach log template · records of
processing (settings page listing what the program stores) · cross-border: portal/relay hosting location documented.
The product supports compliance; it does not replace legal advice.

## 8. Security testing

Unit tests for permission matrix (every route × profile), scope filters, money masking, CSRF, XSS escaping in the UI
kit, upload validation, log secret scanner, erase-order end-to-end (two PCs, chains still verify), backup restore
re-applies erase orders. Independent security review before each release (BAMS practice).
