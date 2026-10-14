# Baseline freeze: version 3.0.0

Recorded on 2026-10-13, before any change for version 4. The version 3 documents are kept unchanged
in [v3/](v3/); the version 2 baseline record is [v3/BASELINE.md](v3/BASELINE.md).

## 1. What is frozen

| Item | Value |
|---|---|
| Repository | `github.com/sandhiyaa031/cognigraph`, branch `main` |
| Commit | `6e5e874` "Add Probabilistic Constraint Graphs project, version 3.0.0" |
| Local tag | `v3.0.0` (created for this freeze; not pushed) |
| Working tree at freeze | clean |
| Untouched copies outside the repository | `archive/original-third-party-backup` (third-party original), `archive/v2.0.0-baseline` (version 2) |
| Environment | Windows 11, Python 3.12.3, numpy 2.2.5, networkx 3.5, matplotlib 3.10.5, pytest 9.1.1, pgmpy 1.1.2, pylint 4.1.3 |
| Seed | 20261013 |
| Tests | 190 passing (`docs/TEST_LOG.txt` at the commit) |

To return to the baseline: `git checkout v3.0.0`.

## 2. Data and configuration of the baseline

| Set | Content | Size |
|---|---|---|
| D1 | 34 programs written for the project, single injected faults | 624 valid, 594 detected |
| D1 two-fault | pairs of injected faults | 410 detected |
| D2 | QuixBugs human-written bugs (commit 4257f44) | 31 |
| D3 | QuixBugs single injected faults | 402 valid, 382 detected |

Configuration: `pcg/config.py` at the commit. Commands: `python -m pcg benchmark` (version 2
experiments), `python -m pcg research` (version 3), `python -m pcg demo`.

## 3. Headline numbers of the baseline

From `results/research/SUMMARY.md` at the commit.

| Set | Metric | Ochiai | Barinel | Metallaxis | Logistic fusion | PCG spectrum | PCG v3 fused |
|---|---|---|---|---|---|---|---|
| D1 | Top-1 | 0.538 | 0.538 | 0.748 | 0.959 | 0.548 | 0.957 |
| D1 stress test | Top-1 | | | 0.549 | 0.771 | | 0.729 |
| D2 (31 human bugs) | Top-1 | 0.376 | 0.381 | 0.305 | 0.575 | 0.381 | 0.511 |
| D2 | MRR | 0.565 | 0.570 | 0.501 | 0.699 | 0.562 | 0.666 |
| D3 | Top-1 | | | | 0.917 | | 0.911 |
| D1 two faults | both in top 3 | | | | | 0.359 | 0.198 |

Probabilities: D1 Brier 0.0145 for the fused model against 0.0141 for logistic fusion; D2 log loss
0.316 against 0.410 (base rate 0.380).

## 4. Artifact fingerprints

| Artifact | SHA-256 |
|---|---|
| `results/benchmark/MANIFEST.json` | `141c0a38e97d13e38b098c0bf5e3d610900a7190c1c3645f0c00011ff81f4d83` |
| Per-file hashes of `results/research` | in `results/research/MANIFEST.json` |
| HumanEvalPack Python split, `python-test.parquet` as downloaded | `ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075` |
| The same, converted to JSON lines | `523fb78ceec3ecec82befe30fb02492575a7fddeca256dbc916b1cb264e1de10` |

## 5. Reproduction performed for this freeze

The open item of the version 3 audit was that two identical runs after the memory-address fix had
not been shown.

| Check | Command | Result |
|---|---|---|
| Second complete research run after the fix | `python -m pcg research` | exit 0, 1,118 s |
| Compared with the run that was committed | per-file hashes in the two manifests | **22 of 24 files identical** |
| The two that differ | `cost.json`, `SUMMARY.md` | only the wall-clock seconds in the cost section (44 and 36 s; 269 and 276 s) |

So the version 3 research results, including all five human-bug files, reproduce bit for bit. No
discrepancy with the committed numbers was found.

## 6. Known limitations of the baseline (unchanged, from the version 3 audit)

1. Exact inference needs at most 22 executed statements.
2. The mutation-evidence tables assume one fault; with two faults fusion is worse than no fusion.
3. Tests are treated as independent given the faults.
4. With coverage alone the model equals Ochiai and Barinel.
5. With mutation evidence it equals logistic regression on injected faults and trails it in the
   stress test.
6. 31 human-written bugs; the Top-1 gain there is not statistically significant.
7. No comparison with SmartFL; no LLM evaluation.

## 7. Rule for the work that follows

Version 4 adds modules and a results folder (`results/v4`). It does not change any code path used
by `results/benchmark` or `results/research`; this is checked at the end by re-running both and
comparing the fingerprints above.
