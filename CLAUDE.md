# Self Business OS (working name) — rules for every change

Owner: Mohamed Fawzy. Users are self-employed people and teams of 1–4 who are **not technical**.
Start with `AGENT_HANDOFF.md`, then `TASKS.md`. Load the project skill `.claude/skills/self-business-dev/SKILL.md`.

## Always
1. Update in the same pull request as the code: `DEVELOPMENT_HISTORY.md` (newest first: what, why, mistakes,
   lessons), `TASKS.md` (tick + test map), `IDEAS.md` (new reusable idea), the skill (new rule/pitfall/command),
   the design doc that changed (`docs/*`), help texts for changed screens.
2. Test before every push; add a regression test for every bug fixed.
3. UI work: run it in a real browser, screenshot the visual matrix (`docs/DESIGN.md` §10), critique, fix.
4. Bigger changes: independent review (correctness, distributed, security) → verify and fix each finding.
5. Simplicity: one clear action per screen, plain words. UI strings only through i18n keys (Arabic + English);
   RTL via logical CSS properties.
6. Replies to the owner: short simple Egyptian Arabic with fitting emojis, no English words mixed in, conclusion first.

## Never
- Never share or copy database files between PCs; never put SQLite on a network folder.
- Never roll back the journal or silently delete user data. Normal delete = soft delete; restore = new change.
  Physical removal only through the legal-erasure path (`docs/SECURITY.md` §5).
- Never store money as floats; never edit an issued document or a payment in place.
- Never trust the UI for permissions: every route checks permission, scope and money visibility on the server.
- Never write passwords, tokens, link tokens, keys or licence keys into logs.
- Never let a personal link or portal link carry admin rights.
- Never put a brand name, logo, or tax law in code (brand → settings; tax → connector).
- Never copy code from copyleft or source-available projects; check the licence before any reuse.
- Never commit owner or client data, secrets or real names (the repository is public).
- Never modify the reference repositories (Mr.Ayman-HR, Yousef-Transportation).
- Never push to `main` or force-push; work on the session branch; merge only after review and when asked.

## Tests (grow with Phase 1)
```
python3 -m unittest discover -s tests          # everything
```
