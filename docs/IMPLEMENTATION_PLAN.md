# Implementation plan and status

The rebuild follows eight stages. Each stage lists what was done and which checks were run.
Design decisions and their trade-offs are recorded in [../CHANGELOG.md](../CHANGELOG.md).

| Stage | Goal | Status |
|---|---|---|
| 1 | Audit the original project and record the baseline | Done |
| 2 | Specify the probabilistic model before coding it | Done |
| 3 | Build the core engine: evidence, graph, inference, ranking | Done |
| 4 | Build the mutation benchmark, baselines and evaluation | Done |
| 5 | Implement and validate targeted repair | Done |
| 6 | One-command end-to-end run and demonstration | Done |
| 7 | Documentation and report, written from actual outputs | Done |
| 8 | Final sceptical audit of the finished project | Done, see [FINAL_AUDIT.md](FINAL_AUDIT.md) |

## Stage 1: audit and baseline

* Backed up the original project to `archive/original-third-party-backup/` and verified the copy.
* Re-ran the original scripts in an isolated copy; confirmed all eleven audit findings.
* Outputs: [AUDIT_BEFORE_REBUILD.md](AUDIT_BEFORE_REBUILD.md), [BASELINE_RESULTS.md](BASELINE_RESULTS.md).

## Stage 2: mathematical specification

* Latent variables: one binary fault variable per statement, one latent exposure rate.
* Observed variables: one pass/fail outcome per test, one static-analysis flag per statement.
* Likelihood: noisy-OR over the statements in each test's scope.
* Parameters: estimated from labelled mutants of *other* programs, with add-one smoothing; the
  exposure-rate prior is fitted by EM.
* Inference: exact enumeration; Gibbs sampling as a fallback for large functions.
* Output: [MATHEMATICAL_MODEL.md](MATHEMATICAL_MODEL.md).

## Stage 3: core engine

| Module | Responsibility |
|---|---|
| `pcg/program.py` | Canonical source, compiler diagnostics, statement components |
| `pcg/_runner.py`, `pcg/execution.py` | Isolated test execution with per-test line coverage |
| `pcg/static_analysis.py` | pylint findings, split into behavioural and stylistic |
| `pcg/dependence.py` | Variables, data and control dependence, backward slices |
| `pcg/graph.py` | The constraint graph and its translation into the Bayesian network |
| `pcg/model.py` | The model, exact inference, Gibbs sampling |
| `pcg/estimation.py` | Parameter estimation, EM for the exposure prior |
| `pcg/analysis.py` | The single inference entry point `analyze` |

Checks: `tests/test_model.py` (exact inference against brute force, closed forms and pgmpy),
`tests/test_evidence.py`.

## Stage 4: benchmark and evaluation

| Module | Responsibility |
|---|---|
| `pcg/benchmark_programs.py` | 34 reference programs with hand-written test inputs |
| `pcg/mutation.py` | Ten documented fault-injection operators |
| `pcg/baselines.py` | Chance, execution-only, heuristic, Tarantula, Ochiai |
| `pcg/metrics.py` | Top-k, MRR, EXAM, Brier, log loss, ECE, cluster bootstrap, sign-flip test |
| `pcg/experiments.py` | The six experiments |

Checks: `tests/test_benchmark_mutation.py`, `tests/test_estimation_metrics.py`.

## Stage 5: targeted repair

* `pcg/repair.py`: deterministic single-edit search restricted to the three most suspicious
  statements; every candidate is compiled and run against the full suite in a child process.
* `pcg/llm.py`: optional LLM patch generator behind the same validation. Not run against the live
  API (no credentials); its trust-relevant logic is tested with a stand-in client.

Checks: `tests/test_integrity.py` (repair section), `tests/test_llm.py`.

## Stage 6: integration

* `python -m pcg all` runs every experiment and then the demonstration.
* Results directories are emptied at start and receive a `MANIFEST.json` only on completion.

## Stage 7: documentation

README, MATHEMATICAL_MODEL, EXPERIMENTS, LIMITATIONS, REPRODUCIBILITY, REPORT. Every number in them
is copied from `results/benchmark/SUMMARY.md`, which is generated from the result files.

## Stage 8: final audit

Re-read the finished project against the fifteen acceptance criteria (A to O) and searched for
hardcoded results, leakage, stale artefacts and unsupported claims. Outcome in
[FINAL_AUDIT.md](FINAL_AUDIT.md).

## Not done (future work)

* Real LLM confidence data: none was collected, so the LLM channel is evaluated only with a
  simulated signal.
* Real (non-injected) faults and larger, multi-function programs.
* Dynamic (execution-trace) slicing instead of the static approximation.

# Research phase (version 3.0.0)

The stages above describe the rebuild (version 2.0.0). The research phase followed eight phases of
its own. Each one ended with a document or a verified result before the next began.

| Phase | Goal | Output | Status |
|---|---|---|---|
| 1 | Verify and snapshot the baseline | `research/v3/BASELINE.md`; recoverable copy; independent recomputation | Done |
| 2 | Review the base paper and eight further papers | `research/v3/LITERATURE_REVIEW.md`, `REFERENCE_VERIFICATION.md`, `RESEARCH_GAP_MATRIX.md` | Done |
| 3 | Compare candidate directions and select | `research/v3/RESEARCH_PROPOSAL.md` (five candidates, one primary, one complementary) | Done |
| 4 | Design the model change before coding | `research/v3/MATHEMATICAL_DESIGN.md` | Done |
| 5 | Implement | `pcg/mbfl.py`, `fusion.py`, `barinel.py`, `discriminative.py`, `quixbugs.py`, `research.py`, `research_report.py`; 27 tests | Done |
| 6 | Evaluate | `results/research`; `docs/EXPERIMENTS.md` Part B | Done |
| 7 | Verify and reproduce | `docs/FINAL_AUDIT.md` | Done |
| 8 | Deliverables | README, report, limitations, review guide | Done |

## What was deliberately not done

| Idea | Reason |
|---|---|
| Soft slicing (dependence-structured exposure) | Expected effect near zero on programs this small; richer semantic models already exist |
| Lifted exact inference | No benchmark in reach needs more than 18 statements |
| A type-checker evidence channel | The base paper's own results and this project's measurements say it would carry no information for semantic faults; measured instead |
| Real LLM evidence | No credentials |
| BugsInPy, Defects4J | Setup effort and program size beyond this project |
| Promoting the better-performing ablation to "the proposed model" | It was not the pre-registered model |
