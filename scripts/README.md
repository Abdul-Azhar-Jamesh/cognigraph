# Scripts

| Script | Purpose |
|---|---|
| `check_layout.py` | Lightweight verification: module imports, data and result paths, `MANIFEST.json` checksums of every result folder, relative links in the documents, figure index, archive checksums (`--no-archive` to skip). Writes nothing. |
| `compare_manifests.py` | Compare two result manifests (repeated runs): identical-file count, differing files, unexpected differences. |
| `development/` | Exploratory scripts of the version-4 development stage (`dev_poc.py`, `bic.py`, `diag.py`, `diag2.py`). They produced the Gate-3 numbers in `research/RESEARCH_PROTOCOL.md` section 2 and the model-order table in `research/MATHEMATICAL_DESIGN.md` amendment A1. Not part of the reproducible pipeline; run from the project root with `PYTHONPATH=.`, first argument a pickle cache path (built on first use, ignored by Git). |

The reproducible pipeline itself is the command line: `python -m pcg {benchmark,research,v4,v4-report,v4-synthetic,demo,demo-v4,all}`
(see `docs/REPRODUCIBILITY.md`).
