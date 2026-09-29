# Research — market, open source, technology (Phase 0, 2026-09-29)

Method: web research (vendor sites, official docs, comparison articles, review sites, GitHub), plus a full read of the
two reference repositories (see §5). Vendor comparison pages are biased (many are written by competitors, e.g. Plutio);
we only keep claims that several sources agree on, and we mark single-source claims as such.
The owner's hypotheses (master prompt §19) are checked in §3.

---

## 1. Commercial products

| Product | Problem it solves | People like | People dislike | Where it gets complex | Lesson for us |
|---|---|---|---|---|---|
| **HoneyBook** | client flow for creatives/freelancers: inquiry → proposal → contract → invoice → payment | "Smart Files": one client document that combines proposal + contract + invoice + scheduling, client signs and pays in one place; ready templates; automations built from templates; client portal shows everything that was sent | editor is rigid ("fighting the software" when changing contract terms); payments need a US/Canada bank; not a lead-generation tool | automation builder sequences | ✅ **one combined client document** (quote + terms + deposit invoice) → our "Offer pack". ✅ templates inside the automation builder. ❌ do not lock layout; ❌ do not tie money to one country. |
| **Dubsado** | highly configurable client workflows (forms, contracts, invoices, workflows) | power and flexibility, forms, detailed workflows | "famously complex to set up", days of configuration; interface feels dated; settings three levels deep | workflow configuration, form builder | ✅ power is valued; ❌ **setup cost is the #1 complaint** → our setup is a guided wizard with activity presets; advanced options folded away. |
| **Bonsai** | freelancer suite: proposals, contracts, invoices, time, taxes | all-in-one, contract templates | proposal templates feel locked; US-centric tax layer that international users pay for but cannot use | accounting/tax part | ❌ never put one country's tax law in the core → **tax connector**. |
| **Moxie** | freelancer CRM + projects + invoices | simple, pipeline, invoices | portal, automations, API gated behind higher plan; list-only project views; reviewers report tasks disappearing after updates and invoice reminders breaking silently (single-source: competitor page) | — | ✅ **reliability is a feature**: automation run log, visible failures, never "silently broken". |
| **Plutio** | all-in-one freelancer workspace (projects, tasks, invoices, proposals, portal, automations) | many views (list, board, Gantt), white-label portal, automation triggers on tasks/projects/deadlines | breadth can feel heavy (many modules at once) | module sprawl | ✅ triggers on task/project/deadline events, not only pipeline; ❌ show only the modules the user chose. |
| **Twenty** (open source, AGPL-3.0) | modern open-source CRM (Salesforce/HubSpot alternative) | clean modern UI, custom objects and fields from the UI, workflows (trigger: record created / field changed / schedule; actions: create/update record, email, webhook), command menu, MCP server for AI | sales-team oriented; self-hosting needs Postgres/Redis/Docker | custom objects | ✅ UI quality bar (tables, side panels, command menu); ✅ workflow trigger model; ❌ **AGPL: ideas only, no code** in a closed commercial product. |
| **Dolibarr** (GPL-3.0) | lightweight ERP/CRM for freelancers and micro businesses | easy install on PHP hosting, modules you switch on/off | UI dated, many menus | many modules with overlapping screens | ✅ **modules switched on/off** idea validated; ❌ GPL → ideas only. |
| **ERPNext** (GPL-3.0; Frappe framework MIT) | complete ERP | complete, open | deployment complexity (bench, MariaDB, Redis, reverse proxy), typical rollout 2–4 months | everything | ✅ confirms "strong core + doctypes"; ❌ exactly the "needs a staff member to run it" feeling we must avoid. |
| **Invoice Ninja** (Elastic License 2.0, source-available) | invoices, quotes, recurring invoices, expenses, time, projects, client portal with online checkout | complete invoicing, branded client portal, recurring invoices | self-hosting Laravel stack | payment gateways | ✅ client portal shows invoices/quotes/payments with "approve quote" and "pay"; ✅ recurring invoices; ❌ ELv2 is not open source → ideas only. |

### 1.1 What the market teaches (synthesis)

1. **The journey is the product**, not the contact list: lead → offer → agreement → work → delivery → invoice →
   payment → follow-up → renewal. Every successful product sells this journey.
2. **Combined client documents** (proposal + terms + deposit) remove friction for both sides.
3. **The portal** is valued because the client stops asking "send me the invoice again / where is the file".
4. **Automation must be template-first** and **observable** (run log, failures shown). Silent failures destroy trust.
5. **Setup cost kills adoption** (Dubsado); **rigidity kills retention** (HoneyBook editor).
6. **Country lock-in** is a real complaint for non-US users (HoneyBook payments, Bonsai taxes) → our opening in Egypt/MENA.
7. **Online-only** is universal among competitors → local-first + Arabic + Egyptian payment realities is a real gap.
8. Almost nobody serves **"one person, several activities"** or **after-sale software support for micro companies**.

## 2. Open-source projects (ideas and licences)

Rule: **no code is copied** unless its licence allows closed commercial use *and* the owner approves the dependency.
Copyleft (GPL/AGPL) and source-available (ELv2, Sustainable Use) projects are for **ideas only**.

| Project | Link | Licence | Tech | Useful idea | Code use? | Risk / maintenance |
|---|---|---|---|---|---|---|
| Twenty | github.com/twentyhq/twenty | AGPL-3.0 | TS, NestJS, Postgres | record side panel, command menu, workflow triggers, custom objects | ideas only | — |
| Dolibarr | github.com/Dolibarr/dolibarr | GPL-3.0+ | PHP | module on/off, thirdparty = client+supplier in one record | ideas only | — |
| ERPNext / Frappe | github.com/frappe/erpnext | GPL-3.0 (Frappe MIT) | Python, MariaDB | doctype metadata, "party" concept, payment entries separate from invoices | ideas only | — |
| Invoice Ninja | github.com/invoiceninja/invoiceninja | Elastic License 2.0 | PHP/Laravel | portal actions (approve quote, pay), recurring invoices, credits | ideas only | — |
| InvoicePlane | github.com/InvoicePlane/InvoicePlane | MIT | PHP | quote → invoice conversion, simple numbering groups | allowed (MIT) but different stack; ideas | — |
| Freelancey | github.com/abdisamadjoe/Freelancey | MIT (per repo) | NestJS/Next.js | white-label portal + e-signature flow for freelancers | ideas (stack differs) | young project |
| Kimai | github.com/kimai/kimai | AGPL-3.0 (verify before any use) | PHP | time tracking UX, rates per customer/project/activity | ideas only | — |
| Activepieces | github.com/activepieces/activepieces | MIT core (open-core) | TS | trigger/action "pieces" = our connectors; step test | ideas; MIT would allow | open-core parts differ |
| n8n | github.com/n8n-io/n8n | Sustainable Use License (fair-code) | TS | execution log per run, retry, pinned test data | **no** (not open source) | — |
| cr-sqlite | github.com/vlcn-io/cr-sqlite | MIT | C/Rust ext | column CRDTs in SQLite | rejected (native extension; evaluated as too early for production in late 2025; wrong merge for money) | — |
| PowerSync / ElectricSQL | powersync.com / electric-sql.com | various | need central Postgres | server-authoritative sync | rejected (central server, not peer-to-peer, not offline-first for a team without a server) | — |
| Automerge / Yjs | github.com/automerge, yjs | MIT | Rust/JS | document CRDTs | rejected for relational data; possible later for rich-text notes | native bindings |
| Lucide icons | github.com/lucide-icons/lucide | ISC | SVG | consistent outline icon set | **yes** (ISC allows commercial use; keep licence file) | low |
| Tabler icons | github.com/tabler/tabler-icons | MIT | SVG | large icon set | yes (alternative to Lucide) | low |
| IBM Plex Sans Arabic / Plex Sans | github.com/IBM/plex | SIL OFL 1.1 | fonts | Arabic+Latin matched family | **yes** (bundle with OFL.txt) | low |
| Cairo / Tajawal / Noto Kufi Arabic | Google Fonts | SIL OFL 1.1 | fonts | alternative Arabic fonts | yes | low |
| pyca/cryptography | github.com/pyca/cryptography | Apache-2.0 / BSD | Python + Rust/OpenSSL | Argon2id (since 44.0), AES-GCM, fast Ed25519, X.509 | **candidate single dependency** — owner decision (ADR-011) | wheels per Python version; security updates to follow |

## 3. Owner hypotheses (master prompt §19) — verdict

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Users want one journey, not contact management | **Confirmed** | HoneyBook/Dubsado/Plutio all sell the journey; CRM complaints = "built for sales teams" |
| Client portal matters | **Confirmed, with a twist** | valued by HoneyBook/Invoice Ninja/Plutio users — but a portal needs the internet, which conflicts with local-first → needs a gateway (ADR-009) |
| Automation matters but complex automation scares small users | **Confirmed** | Dubsado setup complaints; HoneyBook builds automations from templates |
| Templates before an advanced editor | **Confirmed** | same |
| Freelancers hate big CRMs; too-simple tools send them back to Excel | **Confirmed** by review patterns; no hard numbers found | review sites, comparison articles |

## 4. Technology research

| Question | Finding | Decision |
|---|---|---|
| Password hashing | OWASP: Argon2id (≥19 MiB, t=2, p=1) first; scrypt (N=2^17, r=8, p=1) if no Argon2id; PBKDF2-HMAC-SHA256 ≥ 600,000 for FIPS. Python stdlib has `hashlib.scrypt` and PBKDF2, **not** Argon2id. `cryptography` ≥ 44 has Argon2id (OpenSSL ≥ 3.2). Measured here: scrypt 2^17 ≈ 0.78 s, PBKDF2 600k ≈ 0.20 s per hash. | ADR-011: scrypt by default (stdlib), Argon2id if the owner accepts `cryptography`; PBKDF2 hashes verified and upgraded at login |
| SQLite over the network | SQLite documents that WAL mode does not work over a network filesystem (all processes must be on the same host); file sharing corrupts. | never; each PC its own DB; sync = logical changesets (BAMS design) |
| SQLite durability | WAL + `synchronous=FULL` (BAMS) gives durable commits; `NORMAL` may lose the last transactions on power loss | keep FULL for business DB and journal |
| Full-text search, Arabic | SQLite 3.45 FTS5 with `unicode61 remove_diacritics 2` works on Arabic text (tested). Arabic needs extra normalisation (أ/إ/آ→ا, ة→ه, ى→ي, tatweel, Arabic-Indic digits) and phone normalisation | FTS5 derived index + our own normaliser (ADR-005) |
| Sync engines 2026 | cr-sqlite early-stage; PowerSync/Electric need central Postgres; Automerge/Yjs document-oriented | keep BAMS journal + deterministic fold (ADR-002) |
| Egypt e-invoice / e-receipt | ETA: B2B e-invoice via REST API (OAuth2 client credentials) with documents **signed by an approved certificate on USB token/HSM**; B2C e-receipt waves extended through 2025; VAT registration threshold changes reported for 2026 (verify with a tax advisor before building) | tax connector port only in V1; Egypt connector later with a local signing helper |
| Egypt data protection | Law 151/2020; Executive Regulations issued by PM Decree 816 on 1 Nov 2025 (consent, records, breach notification, cross-border transfer, direct marketing) | legal-erasure path, retention policies, consent flag on contacts, breach log (SECURITY.md §7) |
| Desktop shell | a local server + the browser works (BAMS); Edge/Chrome `--app=` mode gives a window without browser chrome, no extra dependency | ADR-010 |

## 5. Reference repositories (read-only)

- **Mr.Ayman-HR (BAMS)** @ `5f5b3ce` (v2.4.0): studied fully — see `ARCHITECTURE.md` §3 for the reuse table.
  Fast tests run here: 31/33 pass; the 2 errors come only from the shallow clone (tests read an old commit).
- **Yousef-Transportation (Trip Orders)** @ `1ecc471`: second fork of the BAMS engine (Phase 1a), with a written design
  system (`docs/DESIGN.md`: tokens, light "Daylight"/dark "Night Road", motion table, command palette, shortcuts,
  side panels, slides, tours, settings with live preview) and the gateway idea (Cloudflare Worker + D1 mailbox, office
  PC never reachable from the internet). **The UI is not built in that repository yet**, and the screenshots mentioned
  in the brief were not attached to this session → open question Q3.

Key insight: the owner now has **two copies of the same engine** (BAMS and Trip Orders) and this would be the third.
We extract a **domain-free core** instead of forking again (ADR-002, recommendation R1).

## 6. Sources

- HoneyBook automations and Smart Files: https://www.honeybook.com/automations · https://help.honeybook.com/en/articles/5259476-create-build-and-elevate-smart-files-in-honeybook · https://fast.io/resources/honeybook-client-portal/
- HoneyBook vs Dubsado vs Bonsai: https://www.solopad.io/blog/honeybook-vs-dubsado-vs-bonsai · https://www.plutio.com/compare/honeybook-vs-dubsado · https://thrivelance.com/reviews/bonsai-alternatives/ · https://capterra.com/p/206389/Dubsado/reviews/ · https://sarahworboyes.co.uk/dubsado-vs-honeybook/
- Moxie / Plutio: https://www.plutio.com/compare/plutio-vs-moxie · https://agiled.app/alternatives/moxie
- Twenty: https://twenty.com/ · https://marmelab.com/blog/2026/01/09/open-source-crm-benchmark-2026.html · https://www.dench.com/blog/twenty-crm-review
- Invoice Ninja licence and portal: https://github.com/invoiceninja/invoiceninja · https://invoiceninja.github.io/en/legal/license/
- Dolibarr / ERPNext / Frappe: https://devdiligent.com/blog/dolibarr-erp-guide/ · https://www.erpresearch.com/en-us/erpnext · https://discuss.frappe.io/t/licensing-of-app-made-using-frappe-erpnext/9836
- Open-source freelancer tools: https://github.com/abdisamadjoe/Freelancey · https://github.com/InvoicePlane/InvoicePlane · https://github.com/topics/client-portal
- Automation licences: https://docs.n8n.io/privacy-and-security/sustainable-use-license · https://aicoolies.com/comparisons/activepieces-vs-n8n
- Local-first sync 2026: https://www.smashingmagazine.com/2026/05/architecture-local-first-web-development/ · https://kanopylabs.com/blog/electric-sql-vs-powersync-vs-livestore-local-first · https://verity.salient.community/research/local-first-software-in-2026.html
- OWASP password storage: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- pyca/cryptography Argon2id: https://cryptography.io/en/stable/changelog/ · https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/
- Egypt ETA: https://docs.ecosire.com/odoo-modules/egypt-eta-einvoicing · https://sovos.com/regulatory-updates/global-vat/egypt-tax-authority-extends-e-receipt-obligations-for-b2c-transactions/ · https://www.avalara.com/us/en/vatlive/country-guides/africa-and-middle-east/egypt-vat/egyptian-e-invoicing.html · https://www.vatupdate.com/2026/02/23/briefing-document-podcast-e-invoicing-e-reporting-in-egypt/
- Egypt PDPL: https://www.tamimi.com/law_update_articles/from-policy-to-practice-egypt-issues-executive-regulations-of-the-personal-data-protection-law/ · https://www.bakermckenzie.com/en/insight/publications/2026/01/egypt-important-data-protection-update · https://www.kennedyslaw.com/en/thought-leadership/article/2026/egypt-s-personal-data-protection-law-the-compliance-countdown-has-begun/
- Icons / fonts: https://lucide.dev/license · https://github.com/tabler/tabler-icons · https://github.com/IBM/plex
- Local-first principles: Kleppmann et al., "Local-first software" (2019) — also cited in BAMS `docs/RESEARCH_NOTES.md`.
