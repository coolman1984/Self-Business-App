# Provenance of the harvested engine

Source: `coolman1984/Mr.Ayman-HR` (BAMS) commit `5f5b3ce063ea1446c6daaa3b5b3477d2157d810c`, version 2.4.0, read-only.
Owner of both projects: Mohamed Fawzy (the code is his own, so re-use is allowed).

| File | Change so far |
|---|---|
| `ed25519.py`, `tlscert.py`, `node.py`, `replica.py`, `sync.py`, `nodectl.py`, `xlsx.py`, `journal.py` | prefix rename only (`BAMS`→`SBO`, `bams`→`sbo`) |
| `backup.py` | rename; file-name slicing now uses `PREFIX` (lesson from Trip Orders: a blind rename shortened the prefix and broke position slices) |
| `system.py` | rename; the BAMS v1→journal upgrade path (`_upgrade`, `_boot_*`) removed: this product starts with the journal on day one |
| `store.py`, `auth.py` | rename only for now; domain removal and generalisation are tasks 1.3 / 1.8 |
| `version.py` | to be rewritten |

Every later change to a harvested file is added here with its reason.
