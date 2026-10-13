# Probabilistic Constraint Graphs (PCG)

**22AIE301: Probabilistic Constraint Graphs for Uncertainty-Aware Code Generation and Verification**

Given a small Python function and a test suite, PCG estimates for every statement the probability
that the statement is faulty, says how sure it is, and can repair the most suspicious statements.
The estimate comes from a Bayesian network built from the program, its test runs and, in version 3,
the behaviour of its single-edit variants.

Version 3.0.0 adds a research study with a protocol fixed in advance. Its question: *can a
model-based (Bayesian) combination of spectrum and mutation evidence match a learned black-box
combination, are its probabilities trustworthy, and does either survive the move from injected
faults to bugs written by people?*

## Main results

| Finding | Evidence |
|---|---|
| With coverage evidence only, the model ranks like Ochiai and Barinel | Top-1 0.547, 0.538, 0.538 on 594 injected faults |
| Adding mutation evidence helps on injected faults | Top-1 0.548 to 0.957; 0.729 when the trivially repairing variant is removed |
| On 31 human-written bugs (QuixBugs) the gain is in the same direction but not established | Top-1 0.381 to 0.511, difference +0.130, 95% interval [-0.050, +0.301] |
| A learned (logistic) fusion ranks as well or slightly better | D1 0.959 against 0.957; human-written bugs 0.575 against 0.511, not significant |
| The model-based fusion's probabilities hold up better on unseen programs | Brier 0.020 against 0.029 on QuixBugs mutants (interval excludes 0); on human-written bugs log loss 0.316 against 0.410 |
| The posterior tells when to trust the answer better than Ochiai-based confidence | area under the risk-coverage curve 0.251 against 0.312 on injected faults |
| Two pre-registered hypotheses were refuted | conditioning mutation evidence on coverage context; the size-aware prior |
| With two faults the fused model is worse than the model without mutation evidence | both faults in the top three: 19.8% against 35.9% |

No new algorithm is claimed, and no result about real software projects or language models.
Details: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md); what the results do not show:
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## How it works

```
source code ──► compile check ──► run tests with per-test line coverage ──► pylint
                                        │
                     run every single-edit variant against the tests (version 3)
                                        │
                                        ▼
     constraint graph: statements, variables, tests, diagnostics, mutation evidence
                                        │
                                        ▼
   Bayesian network: fault variable per statement, noisy-OR factor per test,
                     learned likelihood factor per evidence source
                                        │
                                        ▼
          exact inference ──► P(statement faulty | evidence) ──► ranking, abstention
                                        │
                                        ▼
        targeted repair of the top 3 statements ──► re-run all tests ──► accept or reject
```

* **Latent variables:** `F_i`, statement `i` is faulty; `Theta`, how often an executed fault makes a
  test fail.
* **Observed:** pass or fail of every test; pylint's behavioural findings; for each statement, what
  its variants do to the failing and passing tests (five levels).
* **Likelihood:** a test passes with probability `(1 - leak)(1 - Theta)^k`, `k` being the number of
  faulty statements it executed (noisy-OR); each other evidence source has a learned table.
* **Parameters:** estimated from labelled faults of *other* programs; never typed in.
* **Inference:** exact, by summing over all fault configurations.

Mathematics: [docs/MATHEMATICAL_MODEL.md](docs/MATHEMATICAL_MODEL.md) (version 2 model, worked
example) and [research/MATHEMATICAL_DESIGN.md](research/MATHEMATICAL_DESIGN.md) (version 3
extension, worked example).

## Install

Python 3.10 or newer. From this folder, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For the research experiments, clone the external benchmark next to this folder:

```powershell
git clone --depth 1 https://github.com/jkoppel/QuixBugs.git ..\QuixBugs
```

No API key is needed.

## Run

| Command | Purpose | Time |
|---|---|---|
| `python -m pytest` | 190 automated tests, including the mathematical ones | 2.5 min |
| `python -m pcg benchmark` | version-2 experiments, `results/benchmark` | 6 min |
| `python -m pcg research` | research experiments, `results/research` (needs QuixBugs) | 20 min |
| `python -m pcg demo` | demonstration, `results/demo` | 1 to 2 min |
| `python -m pcg all` | all of the above except the tests | 30 min |
| `python -m pcg analyze FILE --function NAME --tests TESTS.json` | analyse your own function | seconds |

Details: [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Project layout

```
pcg/
  program.py, _runner.py, execution.py   source handling, isolated test runs, coverage
  static_analysis.py, dependence.py      pylint evidence; variables, dependence, slicing
  mbfl.py                                mutation analysis: evidence levels, Metallaxis, MUSE
  graph.py                               the constraint graph and its Bayesian network
  model.py, estimation.py, fusion.py     the model, exact inference, parameter estimation
  analysis.py                            analyze(): the single inference entry point
  baselines.py, barinel.py               Ochiai, Tarantula, ...; Barinel
  discriminative.py                      logistic-regression baselines, recalibration
  metrics.py                             ranking, calibration, risk-coverage, bootstrap, tests
  mutation.py, benchmark_programs.py     fault injection; 34 reference programs
  quixbugs.py                            loader for the external benchmark
  experiments.py, pipeline.py            version-2 experiments
  research.py, research_report.py        version-3 experiments
  repair.py, llm.py                      targeted repair; optional LLM integration (not exercised)
  demo.py, cli.py, reporting.py, visualize.py
tests/        automated tests
research/     literature review, gap matrix, reference verification, proposal, mathematical design
docs/         report, model, experiments, limitations, reproducibility, review guide, audits
results/      generated by the commands above
```

## Proposal items and their status

| Proposal item | Status |
|---|---|
| Code as a graph of statements, variables, dependences and test constraints | Implemented; the graph defines the Bayesian network |
| Evidence from execution | Implemented: per-test coverage, outcomes, and mutation analysis |
| Evidence from static analysis | Implemented; carried no information about fault locations |
| Evidence from compiler diagnostics | Implemented as a hard gate |
| Bayesian inference combining the evidence | Implemented, exact, validated against brute force, closed forms and pgmpy |
| Uncertainty per component | Implemented; calibration measured in and out of distribution |
| Targeted repair | Implemented as a validated single-edit search |
| Does probabilistic reasoning improve localisation? | Answered: not with coverage alone; with mutation evidence it matches a learned fusion and gives more robust probabilities |
| LLM generation and LLM confidence | **Not evaluated** (no credentials); code exists, simulated study only |

## Documents

| File | Content |
|---|---|
| [docs/REPORT.md](docs/REPORT.md) | The project report |
| [docs/REVIEW_GUIDE.md](docs/REVIEW_GUIDE.md) | Demonstration script, model from first principles, examiner questions |
| [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) | All experiments and results |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Assumptions, failure cases, threats to validity |
| [docs/MATHEMATICAL_MODEL.md](docs/MATHEMATICAL_MODEL.md) | The model, estimation, inference, worked example |
| [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) | Environment, commands, artefacts |
| [docs/FINAL_AUDIT.md](docs/FINAL_AUDIT.md) | Acceptance report, criterion by criterion |
| [research/BASELINE.md](research/BASELINE.md) | State and verification of version 2 before the research phase |
| [research/LITERATURE_REVIEW.md](research/LITERATURE_REVIEW.md) | Review of the base paper and eight further papers |
| [research/RESEARCH_GAP_MATRIX.md](research/RESEARCH_GAP_MATRIX.md) | Gaps, evidence, feasibility |
| [research/REFERENCE_VERIFICATION.md](research/REFERENCE_VERIFICATION.md) | Publication records and what was actually read |
| [research/RESEARCH_PROPOSAL.md](research/RESEARCH_PROPOSAL.md) | Candidates, selection, pre-registered protocol |
| [research/MATHEMATICAL_DESIGN.md](research/MATHEMATICAL_DESIGN.md) | Examination of the model and design of the extension |
| [CHANGELOG.md](CHANGELOG.md) | Changes and design decisions |
| [docs/AUDIT_BEFORE_REBUILD.md](docs/AUDIT_BEFORE_REBUILD.md), [docs/BASELINE_RESULTS.md](docs/BASELINE_RESULTS.md) | The original third-party project |
