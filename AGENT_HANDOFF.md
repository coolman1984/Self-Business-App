# Agent Handoff — read this first

You are continuing **Self Business OS** (working name) for the owner Mohamed Fawzy. He is not technical in his
replies: answer him in short, simple Egyptian Arabic with fitting emojis, no English words mixed in, conclusion first.

## 1. Where things are
| File | What |
|---|---|
| `CLAUDE.md` | rules for every change (always / never) |
| `.claude/skills/self-business-dev/SKILL.md` | working knowledge, commands, pitfalls |
| `TASKS.md` | **where to continue** (first unchecked task) |
| `docs/ROADMAP.md` | phases + success criteria |
| `docs/ARCHITECTURE.md` | layers, BAMS reuse table, ADRs |
| `docs/DATA_MODEL.md`, `SYNC.md`, `SECURITY.md`, `MODULES.md`, `AUTOMATION.md`, `DESIGN.md` | the designs |
| `docs/PRODUCT.md`, `docs/RESEARCH.md` | why |
| `docs/OWNER_BRIEF_AR.md` | what the owner read, his open questions (answers get recorded there) |
| `DEVELOPMENT_HISTORY.md`, `IDEAS.md` | memory and reusable ideas |

## 2. State right now
Phases 0 and 1 are merged into `main`. Phases 2 (design system and shell) and 3 (people, work, timeline, Today v1, import) are implemented on the session
branch `ccr-b21effdb-07jb83` and wait for review and merge — see `TASKS.md` (3.9). Phase 4 (money) is next.
Open owner questions and their defaults: `docs/OWNER_BRIEF_AR.md` §ك. If unanswered, use the default and say so.

## 3. Reference repositories (read-only, never modify)
```
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/coolman1984/mr.ayman-hr /home/user/coolman1984/mr.ayman-hr
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/coolman1984/yousef-transportation /home/user/coolman1984/yousef-transportation
```
Harvest from BAMS commit `5f5b3ce` (v2.4.0). Record every harvested file in `server/core/PROVENANCE.md`.

## 4. The loop for every session
1. `git status`, read `TASKS.md`, read the task's design doc section. Read before you write.
2. Smallest complete slice: code + tests + docs.
3. Run tests; for UI run the app, take screenshots in both languages/themes, critique, fix.
4. Re-read your diff as a hostile reviewer (offline? two PCs? RTL? dark? empty data? permissions via API?).
5. Update `TASKS.md`, `DEVELOPMENT_HISTORY.md`, `IDEAS.md`, the skill, and the design doc you changed.
6. Commit to the session branch, push, never `main`, never force-push. Report to the owner in Egyptian Arabic.

## 5. Traps already known
- Never copy code from GPL/AGPL/ELv2/Sustainable-Use projects (Twenty, Dolibarr, ERPNext, Invoice Ninja, n8n).
- The repository is public (Q1) — never commit owner data, client data, keys, real names.
- Money never in floats. Issued documents never edited. Payments never updated in place.
- A rule/automation must never run on every PC — runner role + deterministic ids.
- Arabic text is 20–30% longer: test clipping at font XL.
