# Threats to validity, version 4

Ordered by how much each one limits what can be concluded. Measured consequences are in
[RESULTS.md](RESULTS.md); this file says what could make those measurements misleading.

## Construct validity: do the measurements mean what they are said to mean?

1. **Multi-fault programs are constructed, not found.** Q2, Q3, E2 and E3 contain faults injected
   by the project's own operators; QHM and EHM combine one human-written bug with one injected
   fault. None of them is a program in which a developer made two mistakes. Faults that co-occur
   naturally may interact in ways injected pairs do not (the survey literature reports interference
   in a majority of multi-fault programs). Data sets of naturally co-occurring faults exist for
   Defects4J and BugsInPy and were not used.
2. **The variants and the injected faults come from the same operators.** For an injected fault the
   exact inverse edit is usually among the variants, so "a restoring variant exists" is far more
   common than for human-written bugs. Every result on injected faults is an upper bound on what
   the variant evidence can give. The breakdown by "has a restoring variant" and the human-written
   sets are the controls.
3. **Ground truth by diff.** A human-written bug is located at the lines that differ from the
   reference solution; a missing statement is blamed on the following one. A different but equally
   valid fix location counts as a miss.
4. **Oracle from the reference solution.** The expected behaviour of a test is what the reference
   solution does, compared by printed representation. For HumanEvalFix only literal-argument calls
   of the benchmark's own tests are used, so the test suites are subsets of the benchmark's.
5. **Mean average precision with mid-ranks** treats ties by their expected position. Methods that
   produce many ties (coverage-only methods on small functions) are neither rewarded nor punished
   for them.

## Internal validity: could something other than the model explain the results?

6. **The model was shaped on D1.** The number of mixture components, the exclusive layer and the
   limit of three faults were chosen there. D1 results are therefore reported as development
   results. The held-out sets were not used for any choice; a four-program smoke test was run on
   them and only its log was read (protocol, deviation D4).
7. **QuixBugs was partly seen before.** QH and Q1 were used in version 3 with the version 3
   methods. The new model was not run on them before the protocol was frozen, but I knew, for
   example, that only 5 of 31 QuixBugs bugs have a restoring variant. HumanEvalFix was never seen.
8. **Baselines are re-implementations.** Barinel, Metallaxis, MUSE and FLITSR were written for this
   project from the papers. Barinel is checked against its paper's worked example; FLITSR against
   the properties the paper states (span, minimal basis), not against the authors' tool.
9. **The logistic baseline is linear and trained on single faults.** A learned model trained on
   multi-fault data, or a non-linear one, could do better. It gets what the proposed model gets:
   single-fault training data.
10. **One seed.** Sampling of cases and bootstrap use one seed. Intervals describe sampling of
    programs, not of seeds.
11. **Implementation errors.** Inference is checked against brute-force enumeration, version 2
    exact inference and simulation from the model; the pipeline around it is checked only by
    ordinary tests.

## External validity: to what do the results generalise?

12. **Small single functions.** Median 5 statements in HumanEval solutions, at most 28; QuixBugs
    functions are of similar size. With five statements, chance alone puts a fault in the top 3
    most of the time. Nothing here speaks about project-scale code.
13. **Two benchmarks of textbook-style programs**, both in Python, both with tests that have exact
    expected values.
14. **Hand-inserted bugs are not field bugs.** QuixBugs bugs come from a programming challenge;
    HumanEvalFix bugs were inserted by the benchmark's authors into correct solutions. They are
    written by people, single, and small.
15. **At most three faults.** Programs with more faults are outside the model as configured.
16. **Deterministic programs with exact oracles.** Flaky tests, tolerances and non-determinism are
    excluded by construction.

## Conclusion validity: are the statistical statements sound?

17. **Program as the unit.** Cases of one program are not independent; all intervals resample
    programs. For QuixBugs that means 31 units and wide intervals.
18. **Multiple comparisons.** Holm correction is applied within the family of H1 only. The many
    secondary tables are descriptive; single "significant" entries among them should not be read as
    findings.
19. **Calibration measures.** ECE depends on binning and can look good for an uninformative
    predictor; it is always reported with the Brier score, its skill against the base rate and the
    log loss. The base rate used for the skill uses the true number of faults of each program,
    which no method knows; it is a reference, not a competitor.
20. **Composite assumptions inside the "exact" model.** The exclusive layer is exact only under
    "one repair per statement" and "one sole cause per test"; the shared exposure rate is a further
    simplification. The synthetic study shows what happens when two of these are broken.

## What was not done

* No comparison with SmartFL, Prosecutor, or any learning-to-rank or neural localiser.
* No language-model evidence.
* No project-scale benchmark, no naturally co-occurring faults.
* No user study; "inspection effort" is a rank, not a person's time.
