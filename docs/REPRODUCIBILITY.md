# Reproducibility

## Environment used for the reported results

| Item | Version |
|---|---|
| Operating system | Windows 11 Home 10.0.26200 |
| Python | 3.12.3 |
| numpy | 2.2.5 |
| networkx | 3.5 |
| matplotlib | 3.10.5 |
| pylint | 4.1.3 |
| pytest | 9.1.1 |
| pgmpy (optional, one cross-check test) | 1.1.2 |

Python 3.10 or newer is required: per-line execution tracing relies on the precise line events
introduced by PEP 626 in Python 3.10.

The exact environment of a run is also written into `results/benchmark/MANIFEST.json`.

## Setup

From the project folder (`cognigraph`), in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On Linux or macOS replace the second line by `source .venv/bin/activate`.

No API key is needed for anything below.

### External data (included)

QuixBugs and HumanEvalPack are kept in `data/external/` (files read by the code only; sources, commits, checksums and
licences in [../data/external/README.md](../data/external/README.md)). Nothing has to be downloaded. Another QuixBugs
location can be given with `python -m pcg research --quixbugs PATH`, another HumanEvalPack file with
`python -m pcg v4 --humaneval FILE`.

## Commands

| Command | What it does | Approximate time (24-core desktop) |
|---|---|---|
| `python -m pytest` | Runs all automated tests | 2.5 minutes |
| `python -m pcg all` | Version-2 experiments, research experiments, demonstration | about 30 minutes |
| `python -m pcg benchmark` | Version-2 experiments only (`results/benchmark`) | 6 minutes |
| `python -m pcg research` | Research experiments (`results/research`); needs QuixBugs | about 20 minutes |
| `python -m pcg demo` | Demonstration only (needs a finished benchmark run; shows more after a research run) | 1 to 2 minutes |
| `python -m pcg analyze FILE --function NAME --tests TESTS.json` | Analyse your own function | seconds |

`TESTS.json` has the form `{"tests": [[arg, ...], ...], "expected": [value, ...]}`. Instead of
`expected` you can pass `--reference OTHER_FILE.py` with a trusted implementation.

## Expected artefacts

`python -m pcg all` creates:

```
results/benchmark/
  MANIFEST.json                    written last; lists a SHA-256 for every file
  SUMMARY.md                       all result tables, generated from the files below
  programs.json                    reference programs, tests, oracle outcomes
  cases.jsonl                      every valid mutant: source, transformation, coverage, outcomes, labels
  excluded_mutants.json            mutants without a result, with the reason
  params_lopo.json                 parameters per held-out program, with the counts behind them
  params_pooled.json               parameters from all mutants (used by `analyze`)
  first_order_per_case.csv         metrics of every method for every detected mutant
  first_order_summary.json         aggregates, by-category table, paired comparisons
  calibration.json                 Brier, log loss, ECE, reliability tables
  fault_free_programs.csv          P(no fault) for the reference programs
  slice_ablation_without_sdl.json  slicing ablation without deletion mutants
  sensitivity.csv                  metrics over hand-set parameter values
  two_fault_cases.jsonl, two_fault_per_case.csv, two_fault_summary.json
  simulated_llm_summary.json       results with the SIMULATED confidence signal
  repair_per_case.csv, repair_attempts.jsonl, repair_summary.json
  fig_method_comparison.png, fig_reliability.png, fig_sensitivity.png
results/research/
  MANIFEST.json, SUMMARY.md        as above, for the research experiments
  d1_per_case.csv, d1_ranking.json           all methods on the project benchmark
  d1_probabilistic.json, d1_selective.json   probability quality, recalibration, risk-coverage
  d1_stress_no_inverse.json                  stress test without the exact-repair variant
  d1_size_prior.json, d1_two_fault_post_hoc.json
  d1_mutation_evidence.jsonl                 levels, contexts, Metallaxis and MUSE per statement
  fusion_params_pooled.json, fusion_params_lopo.json
  external_loading_report.json, external_cases.jsonl
  d2_transfer_*, d2_in_suite_*, d3_transfer_*   QuixBugs results (per case and summary)
  symptoms.json, cost.json
  fig_fusion_ranking.png, fig_fusion_reliability.png, fig_risk_coverage.png
results/demo/
  MANIFEST.json, DEMO.md           transcript of the demonstration
  <case>/faulty_program.py, graph.json, graph.png, repair_report.json, repaired_program.py
```

## What is deterministic

* Mutant generation, test execution, coverage, the oracle: fully deterministic.
* Parameter estimation and exact inference: deterministic.
* Sampling steps (two-fault programs, simulated signal, bootstrap, permutation test, Gibbs): seeded
  with `config.SEED = 20261013` through `numpy.random.default_rng`.
* Tie handling: analytic (expected value), no random tie-breaking.

Running the benchmark twice on the same machine gave identical files: all 22 SHA-256 hashes in the
two manifests match, figures included (see [FINAL_AUDIT.md](FINAL_AUDIT.md)).

The dependency file was also checked in a brand-new virtual environment containing nothing but
`requirements.txt`: the test suite gave 159 passed and 3 skipped (the optional pgmpy cross-check
and two tests that need a finished benchmark run).

## What can differ between machines

* **`cost.json` and section 13 of the research summary** contain wall-clock seconds. They differ
  from run to run by design; every other research result is deterministic.

* **One wall-clock limit.** A runner process is killed after 10 seconds. One mutant
  (`gcd:3:AOR:0`) grows integers without bound and always hits it. On an extremely slow or
  overloaded machine another mutant could hit the limit and be excluded; `excluded_mutants.json`
  shows exactly which. All other termination decisions use a deterministic step count.
* **Floating point.** Different numpy or BLAS builds can change the last digits of probabilities.
  Rankings use scores rounded to nine decimals to make this harmless, but it is not a guarantee.
* **pylint version.** Other versions may report different messages. The version is pinned.
* **Python version.** `ast.unparse` formatting and line-event behaviour are stable for 3.10 to 3.12
  as far as tested here; only 3.12.3 was actually run.
* **File hashes.** Text files are hashed with normalised line endings, PNG files as bytes; PNG
  hashes depend on the matplotlib build.

A fixed seed makes a run repeatable on one setup. It does not make results identical across
library versions.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `StaticAnalysisError: pylint could not run` | pylint is not installed in the active environment: `pip install -r requirements.txt` |
| `FileNotFoundError: ... has no MANIFEST.json` | The benchmark run did not finish. Run `python -m pcg benchmark` and wait for "done" |
| `ModuleNotFoundError: No module named 'pcg'` | Run the commands from the project folder |
| One test reported as skipped | pgmpy is not installed (the cross-check is optional), or the benchmark has not been run yet |
| More entries than expected in `excluded_mutants.json` | The machine was overloaded; close other programs and re-run |
| `FileNotFoundError: QuixBugs was not found` | `data/external/QuixBugs` is missing; restore it from the repository or pass `--quixbugs PATH` |
| The demonstration prints "The research results are missing" | Run `python -m pcg research` first |

# Version 4 (interventional multi-fault model)

Protocol: [../research/RESEARCH_PROTOCOL.md](../research/RESEARCH_PROTOCOL.md). Version 4 adds
commands and result folders; it does not change what `benchmark`, `research` or `all` do.

## Commands

| Command | What it does | Needs |
|---|---|---|
| `python -m pcg v4` | All version 4 experiments; writes `results/v4` | QuixBugs, HumanEvalPack |
| `python -m pcg v4-report` | Rebuilds `summary.json`, `tables/`, `figures/` and `SUMMARY.md` from the raw files in `results/v4` | a finished `v4` run |
| `python -m pcg v4-synthetic` | Controlled study on simulated programs; writes `results/v4_synthetic` | `results/v4/fitted_on_d1.json` |
| `python -m pytest tests/test_v4.py` | The 30 tests of the version 4 mathematics and data handling | nothing |

## Artefacts of `results/v4`

```
per_case.csv               raw: one row per scored case, every method and metric
per_case_secondary.csv     raw: HumanEvalFix under the in-suite and human-fitted conditions
probabilities.jsonl        raw: per-statement probabilities and labels
truncation_check.json      raw: three against four allowed faults
fitted_on_d1.json          parameters estimated on D1 (the transfer condition)
fitted_secondary.json      variant-layer parameters of the secondary conditions
loading_report.json        every benchmark program: used or excluded, and why
cost.json                  variants executed and seconds
summary.json               derived: everything in SUMMARY.md, machine-readable
tables/*.csv               derived: ranking, calibration, paired comparisons
figures/*.png, *.pdf       derived: eight figures
SUMMARY.md                 derived: all tables
MANIFEST.json              SHA-256 of every file; written only when the run completed
```

Raw files are written by `pcg.v4`; derived files by `pcg.v4_report` from the raw files only, so
every figure and table can be rebuilt without re-running an experiment.

## What differs between two runs

`cost.json` (wall-clock seconds) and, through it, the cost section of `summary.json` and
`SUMMARY.md`. Everything else is expected to be identical; the comparison actually made is reported
in [../research/FINAL_RESEARCH_AUDIT.md](../research/FINAL_RESEARCH_AUDIT.md).
