# Changelog and design decisions

## 3.0.0 (2026-10-13): research extension

Version 2.0.0 is preserved in `../pcg-project-v2.0.0-baseline/`. The experiments of version 2.0.0
are unchanged and still reproduce bit for bit (`results/benchmark`). The research work, its
literature basis and its pre-registered protocol are in `research/`.

### What was added

| Area | Addition | Files |
|---|---|---|
| Model | Mutation-analysis evidence as a learned, coverage-conditioned likelihood factor; size-aware prior | `pcg/mbfl.py`, `pcg/fusion.py`, `pcg/graph.py` |
| Baselines | Barinel, Metallaxis, MUSE, hybrid average, two logistic-regression baselines | `pcg/barinel.py`, `pcg/mbfl.py`, `pcg/discriminative.py` |
| Probabilities | Recalibration (Platt scaling on log-odds, nested validation), Brier skill, risk-coverage analysis | `pcg/discriminative.py`, `pcg/metrics.py` |
| Benchmark | QuixBugs loader with oracle check; nested functions, generators and recursion supported | `pcg/quixbugs.py`, `pcg/program.py`, `pcg/_runner.py` |
| Experiments | D1 (project benchmark), D2 (human-written bugs), D3 (QuixBugs mutants), stress test, two-fault post hoc analysis | `pcg/research.py`, `pcg/research_report.py` |
| Tests | 27 new tests | `tests/test_research.py` |
| Command | `python -m pcg research` | `pcg/cli.py` |

No new dependency was added.

### Design decisions of the research phase

**R1. No claim of a new algorithm.** The literature review found Bayesian spectrum-based
localisation (Barinel, 2009) and much richer probabilistic localisers (SmartFL). The contribution
is an evaluated, model-based fusion and a calibration study; see `research/RESEARCH_PROPOSAL.md`.

**R2. Hypotheses and comparisons fixed before the code existed.** They are in
`research/RESEARCH_PROPOSAL.md`, section 5. Two hypotheses were refuted (context conditioning, the
size-aware prior); both are reported.

**R3. The pre-registered model stays the "proposed" model although an ablation beat it.** Changing
the label after seeing the results would be exactly the selective reporting the protocol exists to
prevent.

**R4. Mutation evidence is summarised in five levels with a learned table.** A categorical variable
with a learned likelihood fits the existing model unchanged (it folds into the prior), keeps exact
inference, and needs only eight free numbers.

**R5. Context conditioning.** A statement that no failing test executes cannot be affected by its
variants, so its mutation evidence is forced by coverage. The model sets the likelihood ratio to 1
outside the "executed by all failing tests" context. This turned out to cost accuracy on
single-fault data (R2).

**R6. Logistic regression as the black-box competitor.** It gets the same inputs and the same
training programs, and because it minimises log loss it is the right competitor for probability
quality.

**R7. Barinel candidates are enumerated exhaustively.** The programs are small, so the heuristic
candidate generator of the paper is unnecessary; the maximum-likelihood step is exact.

**R8. QuixBugs oracle.** A test is kept only if the benchmark's correct program reproduces the
benchmark's expected output; the oracle is then that program's behaviour. The nine programs with
object-graph inputs are excluded.

**R9. Stress test for the circularity of mutation evidence on injected faults.** The exact-repair
variant is removed from the analysis, in training and evaluation. It is reported as a stress test.

**R10. Version 2 code paths were left untouched.** New behaviour is behind options that default to
the old behaviour, and the old result files are checked to be identical.

## 2.0.0 (2026-10-13): complete rebuild

The original thirteen scripts were replaced by the `pcg` package. The original project is
preserved unchanged in `../pcg-project-original-backup/`.

**R11. Behaviour signatures no longer contain memory addresses.** The QuixBugs program `flatten`
returns generator objects whose printed form includes an address, so signatures differed between
processes and every variant of that program appeared to change every test. `stable_repr` in
`pcg/_runner.py` masks addresses. Effect: on the human-written bugs the Metallaxis baseline moved
from Top-1 0.289 to 0.305; the proposed model's numbers did not change.

### Stage log

| Stage | What changed | Checks run |
|---|---|---|
| 1 Audit | Backup made and verified; original scripts re-run in isolation; `docs/AUDIT_BEFORE_REBUILD.md`, `docs/BASELINE_RESULTS.md` written | Original test: 1 passed. Four moved-bug counterexamples all returned line 4 = 0.72 |
| 2 Specification | Model defined: fault variables, noisy-OR test factors, unary evidence factors, latent exposure rate | Worked example enumerated by hand and matched by the code |
| 3 Core engine | `program`, `execution`, `_runner`, `static_analysis`, `dependence`, `graph`, `model`, `estimation`, `analysis` | `tests/test_model.py`, `tests/test_evidence.py` |
| 4 Benchmark | 34 programs, 10 mutation operators, 5 baselines, metrics, 6 experiments | `tests/test_benchmark_mutation.py`, `tests/test_estimation_metrics.py` |
| 5 Repair | Deterministic targeted repair; optional LLM generator behind the same validation | `tests/test_integrity.py`, `tests/test_llm.py` |
| 6 Integration | `python -m pcg all`; manifest-guarded results directories | Full pipeline run; manifest and summary consistency tests |
| 7 Documentation | README, model, experiments, limitations, reproducibility, report | Numbers copied from the generated `results/benchmark/SUMMARY.md` |
| 8 Final audit | `docs/FINAL_AUDIT.md` | Acceptance criteria A to O reviewed one by one |

### Design decisions

**D1. A statement is the unit of fault.** Components are statements of one function, identified by
their line in the canonical source (`ast.unparse` output, one statement per line). Trade-off:
faults inside a long expression are located only to the statement; multi-function programs are out
of scope.

**D2. Noisy-OR likelihood for test outcomes.** A test passes only if every faulty statement in its
scope independently "fails to show" (probability `1 - theta` each) and no unmodelled cause
intervenes (probability `1 - leak`). Chosen because it is the simplest model in which several
faults can explain one failure, it has two interpretable parameters, and it is the standard
model in Bayesian diagnosis. Trade-off: it cannot represent faults that cancel each other out.

**D3. Parameters are estimated, never typed in.** Prior, leak, exposure rate and the static-analysis
likelihoods are estimated from labelled mutants of the *other* programs (leave-one-program-out)
with add-one smoothing. Trade-off: the estimates describe this mutation benchmark, not real
software.

**D4. Exact inference by enumeration.** Functions in the benchmark have at most 16 statements, so
all fault configurations can be summed exactly. A Gibbs sampler exists for larger functions and is
validated against exact inference. Trade-off: exact inference is exponential in the number of
executed statements (limit: 22).

**D5. The exposure rate is latent (added after the first full run).** The first version used one
fixed `theta` for every fault. Its results on the benchmark were: equal Top-1 to Ochiai, clearly
worse Top-3 and MRR, and a log loss worse than predicting the base rate, with over-confident high
probabilities. The cause is that faults differ widely in how often they make a test fail, so a
single `theta` punishes a statement far too hard for each passing test that executed it. The model
was therefore extended: `theta` gets a discrete prior, fitted by EM on the training programs, and is
summed out. The fixed-`theta` model is kept as the ablation `pcg_fixed_theta`, so the effect of this
change is visible in every results table. **This revision was made after looking at benchmark
results. The benchmark is therefore not an untouched test set for this decision** (see
`docs/LIMITATIONS.md`).

**D6. `unnecessary-pass` is not evidence (changed after the first full run).** The deletion operator
replaces a statement by `pass`, and pylint reports `unnecessary-pass` on exactly that line. In a
development run this made static analysis look very informative, purely because it revealed where
the benchmark had injected the fault. The message is now excluded and a test guards the exclusion.
That development run is not part of the reported results.

**D7. Dependence slicing is an ablation, not the default.** Restricting a test's scope to its
backward dependence slice is the principled way to let variables and control flow influence
inference, but static slicing cannot see deleted statements. It is implemented, tested and
evaluated (`pcg_slice`); the default scope is plain coverage because that performed better.

**D8. Ties are scored by expectation.** When several statements have the same score, every ranking
metric is its expected value under a random tie-break. Scores are rounded to nine decimals first so
floating-point noise cannot break a tie. This is deterministic and identical for all methods.

**D9. The program is the statistical unit.** Mutants of one program are not independent. Confidence
intervals resample whole programs, and the paired test compares per-program mean differences.

**D10. Step limit instead of a per-test time limit.** A test is stopped after 20,000 executed lines,
which makes "this test did not terminate" a deterministic outcome. A 10-second wall-clock limit per
runner process remains as a safety net; one mutant (`gcd:3:AOR:0`, runaway integer growth) hits it
and is excluded and reported.

**D11. Repair is a search over single edits.** The deterministic repairer tries the mutation
operators as patches on the three most suspicious statements. It needs no API and its results are
reproducible. Trade-off: it can only fix faults that are one edit away, and the patch space
overlaps the fault-injection space, which makes repair rates optimistic (see LIMITATIONS).

**D12. No LLM calls in the evaluated pipeline.** No API key was available. The LLM-confidence
channel is implemented in the model (a learned likelihood over score bins) and studied with a
clearly labelled simulated signal; real LLM evidence is future work.

### Removed

`generate.py`, `parse_output.py`, `build_graph.py`, `evidence_execution.py`, `evidence_static.py`,
`bayesian_fusion.py`, `visualize_graph.py`, `repair.py`, `review_function.py`, `score_function.py`,
`rank_codebase.py`, `pr.py`, `problem.py`, `test_problem.py`, all generated JSON/GML/PNG/TXT files,
`.coverage`, `reviews/`, `sample_code/`.
