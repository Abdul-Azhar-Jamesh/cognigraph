# Cleanup report: workspace reorganised into `cognigraph/`

Date 2026-10-14. Before: five folders in `Probabilistic reasoning/` (`pcg-project-main`, `pcg-project-original-backup`,
`pcg-project-v2.0.0-baseline`, `QuixBugs`, `HumanEvalPack`). After: one folder, `Probabilistic reasoning/cognigraph/`.

## Moved

| From | To | How verified |
|---|---|---|
| `pcg-project-main/` (active project, Git repository with the tag `v3.0.0`) | `cognigraph/` (renamed in place; `.git`, `.venv` and everything else untouched) | `git log`, `git tag`, `git remote` unchanged; the virtual environment still starts |
| `pcg-project-original-backup/` (47 files) | `cognigraph/archive/original-third-party-backup/` | SHA-256 of all 47 files computed before and checked after the move |
| `pcg-project-v2.0.0-baseline/` (90 files) | `cognigraph/archive/v2.0.0-baseline/` | SHA-256 of all 90 files computed before and checked after the move |
| `HumanEvalPack/` (3 files) | `cognigraph/data/external/HumanEvalPack/` | copied, `diff -r` identical, hashes equal the recorded ones; then the original folder was removed |
| `QuixBugs/` (clone at commit `4257f44`) | `cognigraph/data/external/QuixBugs/` (the parts the code reads, see below) | copied, `diff -r` identical for `json_testcases/` (31), `python_programs/` (50), `correct_python_programs/` (50) and three files; clone had no local changes |

## Added (no existing content changed by these)

`data/external/README.md` (sources, commits, checksums, licences), `scripts/` (`check_layout.py`, `compare_manifests.py`,
`development/` with the four exploratory scripts of the version-4 development stage), `figures/README.md` (index; figures stay
next to their manifests, one authoritative copy each), `archive/README.md` and `archive/SHA256SUMS.txt`,
`results/reproducibility/` (manifests of the repeated runs), this report.

## Updated for the new location

* `pcg/config.py`: `QUIXBUGS_DIR` and `HUMANEVALPACK_FILE` now point to `data/external/...` (they pointed to sibling folders).
  Comments and help texts in `pcg/cli.py`, `pcg/quixbugs.py`, `pcg/demo.py` follow.
* `docs/REPRODUCIBILITY.md` (data are included; nothing to clone or download), `README.md` (layout, commands, document list),
  `CHANGELOG.md`, `docs/AUDIT_BEFORE_REBUILD.md`, `docs/BASELINE_RESULTS.md`, `docs/IMPLEMENTATION_PLAN.md`,
  `research/BASELINE_FREEZE.md`, `research/v3/BASELINE.md`: references `../pcg-project-...` became `archive/...`.
* `.gitignore`: `archive/` and `*.pkl` are ignored (the archive is local only).
* `docs/TEST_LOG.txt`: new log (221 passed); the user's interpreter path in one library warning was replaced by `<python>`.
* The package was **not** moved into `src/`: `python -m pcg` and all imports keep working unchanged, which the task rated higher
  than the layout convention.

## Retained

Everything under `results/` (every manifest verified), all of `research/` including `research/v3/`, `docs/`, `tests/`, `data/legacy/`,
Git history (`7ecdedc`, `6e5e874`) and the local tag `v3.0.0`, `.venv`.

## Archived (local, read-only, checksummed, not in Git)

`archive/original-third-party-backup/` (the project as received; the only copy) and `archive/v2.0.0-baseline/` (version 2 is not
in the Git history, which starts at version 3.0.0).

## Deleted (each only after the verification stated)

| Item | Why it was safe |
|---|---|
| `QuixBugs/` clone (Java programs and tests, `python_testcases/`, `tester.py`, paper PDF, CI files, `.git`) | not read by any code or test (searched); the clone had no local changes and sits at the recorded upstream commit `4257f44b...`, so it can be re-cloned exactly; everything the code reads was copied and compared |
| `HumanEvalPack/` original folder | byte-identical copy in `data/external/HumanEvalPack/` |
| Regenerated copies of `results/benchmark`, `results/demo`, `results/research` | restored from the committed v3.0.0 versions with `git checkout`: the re-runs had changed only line endings and wall-clock seconds. Their manifests were saved first in `results/reproducibility/` |

No caches, `__pycache__`, temporary or obsolete generated files existed in the project folder. No document was deleted.

## Verified

| Check | Result |
|---|---|
| `python -m pytest` from `cognigraph/` | **221 passed** |
| `python scripts/check_layout.py` | 38 modules import; config paths exist; the 7 result folders match their `MANIFEST.json` (benchmark 22, demo 20, demo_v4 10, research 24, v4 29, v4_sensitivity 3, v4_synthetic 6 files); links in the documents resolve; 19 listed figures exist; 137 archive files verify |
| Pipeline from the new location | `run_v4` smoke run (2 programs per benchmark) loaded both data sets from `data/external`, ran all stages and wrote tables and figures (scratch folder, removed) |
| QuixBugs loader | 31 programs load; oracle check passes |
| v3.0.0 and baselines | tag and commit present; `results/benchmark` manifest unchanged (`141c0a38...`) |

## Not done, and why

* Full re-run of the 2-hour experiments from the new location (paths proven by the smoke run and by the loaders; results
  are checksummed).
* `docs/REVIEW_GUIDE.md` and `docs/FINAL_AUDIT.md` still describe version 3 (content issue, not a path issue); left untouched.
* No `src/` layout (see above).
