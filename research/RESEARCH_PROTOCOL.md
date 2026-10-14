# Research protocol, version 4 (pre-registration)

Frozen on 2026-10-13, after the development experiments in section 2 and **before the new model was
run on any held-out data set** of section 4. Deviations are appended in section 11 with their
reason; the text above them is not edited.

## 1. Research question

Can a Bayesian fault-localisation model that treats program variants as interventions localise
faults when the number of faults is unknown, using parameters estimated only from single-fault
programs, and are its probabilities usable?

Background and novelty argument: [RELATED_WORK_AND_NOVELTY.md](RELATED_WORK_AND_NOVELTY.md).
Model: [MATHEMATICAL_DESIGN.md](MATHEMATICAL_DESIGN.md).

## 2. What was done on development data (not evidence for the hypotheses)

Development data: D1, the project's own 34 programs, 594 detected single-fault mutants and 410
detected two-fault programs. All parameters leave-one-program-out. These data shaped the model, so
results on them are reported as development results only.

Gate 3 criteria announced in advance: abandon the direction if the new model (a) does not beat the
spectrum-only model and Barinel on "both faults in the top 3" for two-fault programs, or (b) loses
more than 0.02 single-fault Top-1 against the version 3 fused model.

| Version tried | Single-fault Top-1 | Two-fault: first fault Top-1 | both in top 3 | Decision |
|---|---|---|---|---|
| Version 3 fused (reference) | 0.957 | 0.351 | 0.198 | |
| PCG spectrum only | 0.548 | 0.390 | 0.359 | |
| MUSE (best classical on two faults) | 0.746 | 0.602 | 0.441 | |
| Composite layer, 2 non-repair kinds | 0.935 | 0.722 | 0.393 | (a) met, (b) missed by 0.002; diagnosis below |
| Composite layer, 5 kinds, 1 or 3 repair kinds | 0.919 to 0.929 | 0.68 to 0.70 | 0.43 to 0.45 | no improvement from richer mixtures |
| **Exclusive layer, 5 kinds, 1 repair kind** | 0.935 | 0.668 | 0.471 | (a) met, (b) missed by 0.002 |

Diagnosis of the composite layer: single-fault log loss 0.143 against 0.074 for version 3. Cause as
predicted in section 7 of the design: two repairs of different statements were both credited with
fixing the same test. The exclusive layer removes that approximation; log loss fell to 0.074.

**Criterion (b) was missed** (loss 0.022, limit 0.02). I continue anyway and record this as a
judgement call, for one reason: the loss is concentrated in cases where one statement has a full
repair and others have partial ones, which is exactly the evidence pattern that two faults also
produce. A model that allows several faults must pay there. The 0.02 margin is **kept unchanged**
as hypothesis H2 below and may well fail on held-out data.

Choices fixed from development data: exclusive layer; 5 non-repair kinds (smallest number within
100 BIC points of the minimum over 2 to 7); 1 repair kind (2 kinds changed nothing); temperature
`tau = 1` (0.5 gave no consistent gain); at most `c = 3` faults; prior `mu / n` with `mu` estimated
(equal to 1 on single-fault data).

## 3. Hypotheses

| | Hypothesis | Supported when |
|---|---|---|
| **H1 (primary)** | On held-out two-fault programs the interventional model (IV) has a higher mean average precision than each of: version 3 fused, PCG spectrum only, MUSE, FLITSR\* on Ochiai, logistic fusion | For a data set: the 95% interval of the paired difference excludes zero and the Holm-adjusted p value is below 0.05, for that baseline. Tested on Q2 and E2 (10 comparisons in the family) |
| **H2** | On held-out single-fault mutants IV loses at most 0.02 Top-1 against version 3 fused | Lower end of the 95% interval of the difference above -0.02, on Q1 and on E1 |
| **H3** | On human-written single bugs, with all parameters from D1, IV has a higher MRR than PCG spectrum only | 95% interval of the difference excludes zero, on E0 (QH is reported; too small to decide) |
| **H4** | When the number of faults is unknown (pooled 1, 2 and 3-fault programs, each program weighted equally) IV has the highest mean average precision of all methods | IV first, and interval of the difference to the runner-up excludes zero, on Q-mix and E-mix |
| **H5** | IV's probabilities beat the base rate (Brier skill above 0) on every held-out set, and its Brier score is lower than version 3 fused on two-fault sets | As stated; interval of the paired difference for the comparison |
| **H6** | Limiting to three faults does not distort two-fault results: marginals with `c = 3` and `c = 4` differ by less than 0.05 in at least 95% of sampled two-fault cases | As stated, on 100 sampled cases with at most 14 executed statements |
| **H7** | The posterior expected number of faults separates multi-fault from single-fault programs | Area under the ROC curve above 0.5 with interval excluding 0.5, on Q-mix and E-mix |

A hypothesis that does not meet its condition is reported as **not supported**. No hypothesis is
re-worded afterwards.

## 4. Data

Development: D1 (see section 2).

Held-out. "Q" sets come from QuixBugs (31 programs with JSON tests), "E" sets from HumanEvalFix
(the Python split of HumanEvalPack, 164 problems, one hand-inserted bug each).

| Set | Content | Sampling |
|---|---|---|
| QH | QuixBugs human-written bugs | all 31 |
| Q1 | single-fault mutants of the correct QuixBugs programs | 15 per program (the version 3 set D3) |
| Q2, Q3 | two-fault and three-fault mutants | up to 15 and 10 per program, faults on different lines, seeded |
| QHM | the human bug plus one injected fault on another line | up to 10 per program |
| E0 | HumanEvalFix human-written bugs | all usable |
| E1, E2, E3 | one, two, three injected faults in the canonical solution | up to 8, 8 and 4 per program |
| EHM | the human bug plus one injected fault | up to 4 per program |
| Q-mix, E-mix | union of the 1, 2 and 3-fault mutant sets of the benchmark | |

Only cases in which at least one test fails are scored (a localiser has nothing to explain
otherwise); the number of undetected cases is reported.

**HumanEvalFix loading rules.** Test inputs are the calls of the function found in the benchmark's
own `check` function whose arguments are literals made of numbers, strings, booleans, `None`, lists
and string-keyed dictionaries (the runner passes arguments as JSON). Duplicates are dropped. The
expected behaviour of a test is the behaviour of the canonical solution. A problem is excluded,
with the reason recorded, if: it cannot be parsed or uses a nested class; fewer than 3 test inputs
remain; the canonical solution raises or exceeds the step limit on a remaining input; the buggy
version does not differ from the canonical one inside the function; or its function has the same
name as a program of D1 (guard against overlap between training and test programs).

Ground truth: lines of the canonical buggy source that differ from the correct source; for a
missing statement, the statement that follows (convention of Pearson et al., as in version 3). For
hybrids and mutants: the union of the changed lines. A fault "on another line" means a line that is
not already a ground-truth line.

## 5. Training, validation and test separation

* **Primary condition, "transfer"**: every learned quantity (model parameters, variant layer,
  version 3 tables, logistic regressions) is estimated once on all of D1 and applied unchanged to
  every held-out set. No held-out label is used anywhere.
* **Secondary condition, "in-suite"**: for E sets, estimated on the single-fault mutants (E1) of
  the *other* HumanEval problems, 5-fold by problem.
* **Secondary condition, "human-fitted"**: for E0 only, the variant layer is estimated on the human
  bugs of the other problems (5-fold by problem), everything else from D1. This measures how much
  of any shortfall on human bugs is due to `alpha` being learned from injected faults.
* There is no hyperparameter search on held-out data. The architecture choices of section 2 are
  frozen. The logistic baselines keep the ridge penalty 1.0 of version 3.

## 6. Methods compared

All methods receive the same inputs: per-test coverage, test outcomes and the outcomes of the same
variants.

| Method | Evidence | Note |
|---|---|---|
| Ochiai, Tarantula | coverage | |
| Barinel | coverage | designed for multiple faults |
| FLITSR and FLITSR\* on Ochiai | coverage | multi-fault method of Callaghan and Fischer (2023), re-implemented from the paper |
| Metallaxis, MUSE, hybrid average | variants (+ coverage) | |
| Logistic regression: spectrum, fusion | coverage / all | learned on D1 |
| PCG spectrum only (size-aware prior) | coverage | version 2 model |
| PCG version 3 fused | all | single-fault tables |
| **IV (exclusive layer, c = 3)** | all | the proposed model |
| Ablations: IV composite layer; IV with `c = 1` and `c = 2`; IV without variants; IV with the prior probability of each extra fault halved and quartered | | |

Not included, with reasons: SmartFL and Prosecutor (Java, Defects4J tool chains; no Python
implementation); LLM-based localisers (no API access; contamination risk on HumanEval).

## 7. Metrics

* **Mean average precision (primary).** For one program with fault set `T` and scores `s`:
  `AP = (1/|T|) * sum_{t in T} |{u in T : r(u) <= r(t)}| / r(t)`, where `r` is the mid-rank (ties
  share the average of their positions). With one fault this is the reciprocal rank.
* First-fault Top-1 and Top-3; all faults within the top 3 and top 5; mean rank of the faults.
* Probabilities: Brier score, skill against the base rate `(number of faults)/n` per program, log
  loss, ECE (10 bins), reliability tables.
* Selective localisation: risk-coverage curve of "the top statement is faulty" ordered by the top
  posterior; AURC.
* Cost: variants executed, seconds, configurations enumerated.

## 8. Statistics

The unit is the program (problem), not the mutant: mutants of one program share code and tests.
Intervals: percentile bootstrap over programs, 2,000 resamples, seed 20261013, case means within a
resampled program. Tests: paired sign-flip permutation on per-program mean differences, 10,000
permutations. Multiple comparisons: Holm within the family of a hypothesis. Effect size: the mean
difference itself.

Power. QuixBugs has 31 programs; differences below about 0.10 in MAP are unlikely to be detected
there. HumanEvalFix has about five times as many programs. No formal power analysis is possible
before the variance of the new metric is known; the intervals are the answer.

## 9. Ablations and sensitivity

Listed in section 6. In addition: results by number of faults; by whether a restoring variant
exists for each fault; by program size.

## 10. Decision rules

* H1 not supported on both Q2 and E2 against version 3 fused **and** the spectrum-only model: the
  contribution is unsupported; report it as a negative result and stop developing the model.
* H1 supported against the PCG baselines but not against MUSE or FLITSR\*: the model fixes the
  project's own failure but is not better than existing multi-fault techniques; report exactly that.
* H2 not supported: report the single-fault cost with its interval as the price of the model.
* Any regression on a secondary metric is reported next to the primary one.

Expected run time: about one hour on the development laptop. No GPU, no paid service.

## 11. Deviations

Recorded before the full held-out run was started (no held-out result had been seen):

| # | Deviation | Reason |
|---|---|---|
| D1 | Q2, Q3 and QHM are sampled with up to 10, 6 and 6 cases per program instead of 15, 10 and 10 | Run time: QuixBugs programs are slow to execute. The statistical unit is the program (31), so the loss of precision is small |
| D2 | 5,000 bootstrap resamples and 20,000 permutations instead of 2,000 and 10,000 | The project's existing defaults; more resamples, not fewer |
| D3 | The set called E0 in section 4 is named EH in all outputs | Consistency with QH |
| D5 | The first full run stopped with an error in the static-analysis step (too many file names on one command line) before any case had been scored. Fixed by analysing in chunks of 400. At the same time the wall-clock limit of a runner batch was lowered from 120 s to 20 s for HumanEval programs: building the HumanEval sets had taken 18 minutes because of a few runaway mutants | No result existed yet. A program that exceeds the limit is counted as unusable, as before |
| D6 | The second full run stopped when scoring began, before any result was written: six HumanEval function names are used by two problems each, so two different programs shared one identifier. Each program now has a unique identifier (the function name, with the problem number appended where needed). No problem is excluded for this reason | A data-handling error; no result existed yet. The traceback was the only output read |
| D4 | A smoke test with the first 4 programs of each benchmark was run to check that the pipeline executes. Only its log was read (run times and counts); its result files were not opened | Avoid losing an hour-long run to a crash |
