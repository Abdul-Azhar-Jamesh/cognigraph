# Final audit, version 3.0.0 (research phase)

Date: 2026-10-13. This replaces the audit of version 2.0.0. It was written after the last
end-to-end run and reports what was checked, what was found, and what was **not** checked.

Verdict words: **PASS**, **PASS WITH LIMITATIONS**, **FAIL**. Passing tests shows that the code does
what the specification says. It does not show that the model is scientifically valid; that question
is answered, with mixed results, by the out-of-sample experiments.

## 1. Checks that were executed

| # | Check | Command or method | Result |
|---|---|---|---|
| 1 | Full pipeline runs from a clean results folder | `python -m pcg all` | exit code 0 |
| 2 | Automated tests | `python -m pytest` (log in `TEST_LOG.txt`) | 190 passed, 0 failed, 1 deprecation warning from pgmpy |
| 3 | Version 2 results unchanged by the version 3 code | SHA-256 of `results/benchmark/MANIFEST.json` | `141c0a38…f4d83`, identical to the snapshot in `../pcg-project-v2.0.0-baseline` |
| 4 | Research results reproduce | file hashes of this run against the previous run | 16 of 24 files identical; the 8 others are explained in section 3 |
| 5 | Baseline numbers recomputed without importing the project | standard-library script (research phase 1) | Ochiai reproduced exactly; 502 posteriors match brute force |
| 6 | Exact inference | brute force on 80 random models, two closed forms, pgmpy | all agree (in the test suite) |
| 7 | No ground truth reaches inference | tests on function signatures and on leave-one-program-out fitting | pass |
| 8 | Memory addresses absent from behaviour signatures | new test; inspection of `external_cases.jsonl` | 22 occurrences, all masked as `0x?` |
| 9 | Documentation numbers against generated summary | manual comparison, see section 4 | corrected where they differed |

## 2. Acceptance by phase

| Phase | Criterion | Verdict | Evidence and remarks |
|---|---|---|---|
| 1 | Baseline verified and recoverable before any change | PASS | `research/v3/BASELINE.md`; untouched copy; check 3 |
| 2 | Review based on the papers themselves; stated, inferred and open gaps kept apart | PASS WITH LIMITATIONS | Nine papers read in full; seven cited from their records only and marked so in `REFERENCE_VERIFICATION.md`. Metallaxis and Xie et al. could not be downloaded |
| 2 | No invented gap, no unverified novelty or venue claim | PASS WITH LIMITATIONS | The gap is a search-limited claim and is worded that way. Nobody can prove absence of prior work |
| 3 | At least three candidates, ranked; one primary, at most two complementary | PASS | Five candidates; primary evidence fusion; one complementary (calibration and abstention) |
| 4 | Mathematical design before implementation | PASS | `research/v3/MATHEMATICAL_DESIGN.md`; three later amendments appended, original text kept |
| 5 | Implementation is tested and does not disturb the baseline | PASS | Checks 2 and 3 |
| 6 | Strong baselines | PASS WITH LIMITATIONS | Ochiai, Tarantula, Barinel, Metallaxis, MUSE, hybrid, two logistic regressions. No SmartFL, no LLM-based localiser |
| 6 | Human-written bugs | PASS WITH LIMITATIONS | QuixBugs, 31 bugs. Small, single-line, algorithmic; not project bugs |
| 6 | Protocol not changed after seeing results | PASS | Hypotheses and comparisons fixed in the proposal; the one added analysis (two faults) is labelled post hoc; the better ablation was not renamed "proposed" |
| 6 | Negative results kept | PASS | H3 and H4 refuted, two-fault failure, recalibration under shift: all in EXPERIMENTS, LIMITATIONS and REPORT |
| 6 | The contribution is an improvement over the state of the art | **FAIL** | With coverage alone the model equals Ochiai and Barinel. With mutation evidence it equals logistic regression on injected faults, is behind it in the stress test, and nothing is significant on human-written bugs for Top-1 |
| 6 | Probabilities are trustworthy | PASS WITH LIMITATIONS | Better than the base rate everywhere measured and more robust than the learned model on unseen programs; still miscalibrated (ECE 0.045 on D1, 0.062 on D2) |
| 7 | Reproducible | PASS WITH LIMITATIONS | See section 3 |
| 8 | All deliverables exist and agree with the results | PASS WITH LIMITATIONS | See section 4 |
| - | No paid API, no new dependency, nothing committed or published | PASS | LLM path optional and not run; QuixBugs is the only download |
| - | Real LLM evidence | **FAIL (not done)** | No credentials. Reported as not evaluated |

## 3. Reproducibility of the research results

Comparing this run with the previous one:

* Identical: 16 files, including all D1 and D3 results, calibration, the stress test and the
  two-fault analysis.
* `cost.json` and the cost section of `SUMMARY.md`: wall-clock seconds, expected to differ.
* `external_cases.jsonl`, the four D2 files and one figure: these changed **because of a defect
  that was fixed between the two runs**. The QuixBugs program `flatten` returns generator objects
  whose printed form contains a memory address. Behaviour signatures therefore differed from
  process to process, and every variant of that program appeared to change every test.

Effect of the fix on reported numbers: on D2 the Metallaxis row moved from Top-1 0.289 and MRR 0.493
to 0.305 and 0.501, and the paired difference "fused minus Metallaxis" (MRR) from +0.173 to +0.165.
The proposed model's own D2 numbers did not change (Top-1 0.511, MRR 0.666). The documents were
corrected.

**Not verified:** a second run after the fix has not been made, so bit-identity of the five D2
files between two post-fix runs is expected but not demonstrated. To check it, run
`python -m pcg research` twice and compare the two `MANIFEST.json` files.

## 4. Agreement between documents and results

* Compared with the final `results/research/SUMMARY.md`: the D2 tables in EXPERIMENTS and REPORT
  (all rows), the in-suite sentences, the test count.
* Corrected in this audit: the Metallaxis D2 values in EXPERIMENTS and REPORT; the test count
  (189 to 190) in README and REPORT.
* **Not re-compared line by line in this final pass:** the D1, D3, stress-test and two-fault
  numbers. Their result files are byte-identical to the run from which the documents were written,
  so they cannot have changed, but a transcription error made earlier would not have been caught
  here. `REVIEW_GUIDE.md` quotes rounded values and was written before the final run; none of the
  values it quotes changed.

## 5. Problems found in the research phase and fixed

| Problem | Fix |
|---|---|
| Nested function definitions were not treated as statements | `program.py`, `mutation.py`, `dependence.py` |
| Generators returned by QuixBugs programs could not be compared | Materialised in the runner; JSON value comparison |
| Memory addresses in behaviour signatures | `stable_repr` in `_runner.py`, with a test |
| The Barinel paper's worked example is not the exact maximum | Tested against the exact maximum; recorded as amendment A1 |
| Deleted statements have no variants | Recorded as amendment A2; level 0 in the evidence table |

## 6. Weaknesses that remain

1. The mutation-evidence tables assume a single fault; with two faults the fused model is worse
   than the model without mutation evidence.
2. The 0.96 Top-1 on injected faults is inflated because faults are injected and analysed with the
   same operators. The stress test (0.73) and D2 (0.51) are the honest figures.
3. Thirty-one human-written bugs give wide intervals.
4. Programs have at most 18 statements; exact inference would not scale to project code.
5. The main modelling idea (conditioning on coverage context) was refuted by the data.
6. No language model was evaluated, although the base paper is about language models.

## 7. Overall verdict

**PASS WITH LIMITATIONS** as a university project: the model is specified, the inference is
verified, the experiments are out of sample, and the conclusions say what the data say.

**Not ready for publication.** It would need a benchmark of real project bugs, a state-of-the-art
competitor, a treatment of multiple faults, and approximate inference that scales.
