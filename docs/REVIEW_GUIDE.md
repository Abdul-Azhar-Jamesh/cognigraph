# Review guide: how to present and defend this project

Before the review, run `python -m pcg all` once (about 30 minutes) so that `results/` exists. During
the review only quick commands are needed. Keep these open: `results/demo/DEMO.md`,
`results/research/SUMMARY.md`, and the picture `results/demo/human_bug/graph.png`.

## Part 1. Ten-minute demonstration script

### Minute 0 to 1: the problem and the base paper

> "My base paper makes a language model generate code that always type-checks. Its own Table 3
> shows what remains: with type constraints, between 18 and 70 percent of the programs compile and
> still fail their tests. A type system cannot say *where* such a program is wrong or *how sure* we
> can be. That is what my project estimates."

### Minute 1 to 3: the model

Show `results/demo/human_bug/graph.png`.

* Middle column: statements. Each has a hidden yes/no variable "is faulty".
* Right column: tests, red for failed, green for passed. These are observed.
* An edge from a statement to a test: the test executed the statement.
* Left column: variables; curved edges: data and control dependence.

Write one formula:

```
P(test passes | faults) = (1 − leak) × (1 − theta)^(number of faulty statements the test ran)
```

> "This is a noisy-OR. Each faulty statement the test runs gets an independent chance theta to
> break it. Everything else is Bayes' rule: prior times likelihood, summed exactly over all
> combinations of faulty statements."

### Minute 3 to 6: live demonstration

```powershell
python -m pcg demo
```

Go to the case `human_bug` (QuixBugs `knapsack`). Point out in order:

1. A bug written by a person, in a program I did not write. All parameters were estimated on my own
   benchmark; nothing was fitted to this program.
2. Six of nine tests fail. Every test runs every line, so coverage cannot separate anything: all
   nine statements get 0.161 and Ochiai gives all of them 0.816. **The model says so honestly
   instead of pretending.**
3. The column "Mutation evidence": for line 8, `if weight < j`, one single-edit variant makes all
   tests pass. For the other lines no variant changes a failing test.
4. Fused posterior: line 8 gets 0.991. The ground truth, printed last, is line 8 (`<` should be
   `<=`).
5. The repair step was guided by the coverage-only ranking, tried lines 2 to 4, and failed. The
   fused ranking would have gone straight to line 8.

Then scroll to `original_example` (right, but only 58% sure from coverage) and to `worst_case`
(coverage puts the fault 13th of 16).

### Minute 6 to 7: why the numbers can be trusted

```powershell
python -m pytest tests/test_model.py tests/test_docs_example.py
```

> "The inference is compared with brute-force enumeration on 80 random models, with results I
> derived by hand, and with the library pgmpy. The baseline numbers were also recomputed by a
> script that does not import my code at all."

### Minute 7 to 9: the results

Open `results/research/SUMMARY.md`.

* Section 3 (injected faults): coverage only, my model 0.55 Top-1, Ochiai 0.54, Barinel 0.54. With
  mutation evidence 0.96, logistic regression on the same inputs 0.96.
* Say immediately: "These last numbers are inflated. I inject faults and analyse with the same
  operators, so the exact repair is usually among the variants. Section 4 removes that variant:
  0.73 for my model, 0.77 for logistic regression."
* Section 8 (31 human-written bugs): 0.38 without mutation evidence, 0.51 with it, 0.58 for
  logistic regression. "With 31 bugs the interval of my gain is minus 0.05 to plus 0.30. The
  direction is right; it is not established."
* Section 8, probabilities: my model's log loss 0.32, base rate 0.38, logistic regression 0.41.
  "The learned model becomes over-confident on bugs it was not trained for; the Bayesian model
  degrades more gracefully."

### Minute 9 to 10: what did not work

> "I wrote my hypotheses down before writing the code. Two were refuted. I expected that
> conditioning the mutation evidence on coverage would improve the probabilities; it made them
> worse on every dataset. I expected a size-aware prior to help; it made no difference. And when a
> program has two faults, my fused model is worse than the simple one. All three are in the
> report."

## Part 2. The model from first principles

1. **What is unknown?** For each statement `i`, whether it is faulty: `F_i`.
2. **What do we believe before looking?** `P(F_i = 1) = pi`, about 0.12 (or `1/n` in version 3).
3. **What do we observe?** For each test, pass or fail, and which statements it executed.
4. **How does the unknown produce the observation?** If a test executes `k` faulty statements it
   passes with probability `(1 − leak)(1 − theta)^k`. With `k = 0` it almost surely passes.
5. **Bayes' rule.** `P(F | tests) ∝ P(F) × Π_tests P(outcome | F)`. Enumerate all `2^n` assignments
   `F`, multiply, normalise, and add up the assignments in which `F_i = 1`.
6. **Why not one line at a time?** Two statements in the same failing test compete: if one is
   faulty the failure is explained and the other is less suspect. This is "explaining away".
7. **theta is unknown too.** Some faults break every test that touches them, some break one in
   ten. So theta gets a prior (learned by EM) and is summed out.
8. **More evidence.** Any observation about a single statement, with a likelihood under "faulty"
   and under "fault-free", multiplies that statement's prior odds by the likelihood ratio. Static
   warnings and mutation evidence enter this way.
9. **Where do the numbers come from?** Counting, on faults in other programs whose location is
   known.

Worked examples with all numbers: `docs/MATHEMATICAL_MODEL.md` section 8 and
`research/v3/MATHEMATICAL_DESIGN.md` section 9.

## Part 3. Comparison with the base paper

| | Base paper (Mündler et al., PLDI 2025) | This project |
|---|---|---|
| Goal | Make generated code well-typed | Find out where compiling code is wrong, and how sure we are |
| When | During generation | After generation, once tests have run |
| Kind of constraint | Hard: a token is allowed or not | Soft: evidence changes a probability |
| Formal tool | Prefix automata, type inhabitation search | Bayesian network, noisy-OR, exact inference |
| Evidence | The type system | Test outcomes, coverage, program variants, analyser warnings |
| Guarantee | Sound: output is well-typed if it terminates | None; calibration is measured instead |
| What it cannot do | Detect semantic faults | Prevent faults; it localises them |
| Needs | Token probabilities of an open model | Tests with expected results |
| Evaluation | HumanEval, MBPP, six LLMs | 594 injected faults, 31 human-written bugs |

**The quantitative link.** The base paper: 94% of compile errors are type errors; type constraints
remove more than half of all compile errors; pass@1 then still ranges from 30% to 82%. This project
measured the other side: of 594 detected injected faults, 438 only return wrong values and 42 raise
a type-like error; of 31 human-written bugs, 22 only return wrong values and none raises a
type-like error. A static analyser flagged the faulty line in none of them. These are the faults
type constraints cannot see.

**What was not done.** The project does not extend the base paper's algorithm and does not run a
language model. It is complementary work on the residual problem.

## Part 4. The research gap and why it is defensible

**The gap.** Combining kinds of fault-localisation evidence is known to help and is done by
averaging scores or by learned ranking. The authors of the main combination study list the limits
of that black-box approach. Bayesian localisers exist but nobody, as far as I could find, has
measured whether their probabilities are right, or compared a model-based combination with a
learned one, in distribution and on human-written bugs.

**Why it is defensible.**

* It rests on statements in the papers themselves (Zou et al. §6.5; Pearson et al.; Spiess et al.)
  and on searches recorded in `research/v3/LITERATURE_REVIEW.md`, section 12.
* I do **not** claim a new algorithm. Barinel (2009) is the same family of model, and SmartFL is a
  far richer probabilistic localiser.
* The claim is empirical and comes with its refutations.

**What to say if challenged:** "It is a search-limited claim. If such a study exists, my
contribution is a replication on Python with a pre-registered protocol."

## Part 5. Why each baseline was chosen

| Baseline | Reason |
|---|---|
| Ochiai, Tarantula | The standard formulas; every fault-localisation paper reports them |
| Barinel | The established Bayesian method; the closest prior work to my model. If mine were worse, the modelling would be pointless |
| Metallaxis, MUSE | The standard uses of mutation evidence on its own |
| Hybrid average | The simplest combination of the two families, from Pearson et al. |
| Logistic regression, spectrum only | A learned model on exactly the evidence the coverage-only model has; calibrated by construction |
| Logistic regression, all features | The learned black-box fusion. The fair competitor for the main question, for ranking and for probabilities |
| Base rate `1/n` | The reference any probability must beat |
| PCG v2 and the ablations | To see what each component contributes |

Not included: SmartFL, LLM-based localisers, learning-to-rank beyond a linear pointwise model.

## Part 6. Questions an examiner is likely to ask

### The model

**Q1. What are the random variables?** `F_i` (statement faulty, hidden), `Theta` (exposure rate,
hidden), `T_j` (test outcome, observed), `A_i` (static flag, observed), `M_i` (mutation evidence
level, observed).

**Q2. Write the joint distribution.**
`P(F, Theta, T, A, M | K) = P(Theta) Π_i [P(F_i) P(A_i|F_i) P(M_i|F_i,K_i)] Π_j P(T_j | F_{S_j}, Theta)`.

**Q3. Why noisy-OR?** A test fails if any faulty statement it runs shows itself. Noisy-OR says that
with two parameters instead of a table of size `2^k`, and lets several faults explain one failure.

**Q4. What is the leak for?** Failures with no modelled cause. Without it a failing test whose
statements are all innocent would have probability zero.

**Q5. Is inference exact?** Yes: enumeration of `2^a` configurations times 10 values of theta, in
log space; `a` at most 18 here, limit 22. Beyond that the code falls back to Gibbs sampling.

**Q6. How do you know the inference is right?** Brute force on 80 random models, two closed forms,
pgmpy, and an independent script that recomputed 502 posteriors from the raw records.

**Q7. Does a correct inference mean a correct model?** No. Those are different questions. The
second is answered by calibration on data the parameters never saw, and there the model is only
moderately good.

**Q8. Which assumptions are false?** Tests are not independent given the faults; faults are not
independent; coverage is not fixed; and the mutation tables assume a single fault. Each is in
LIMITATIONS with its measured consequence.

**Q9. Why is theta random?** With a fixed theta the log loss was worse than the base rate. Faults
differ in visibility; a prior over theta, fitted by EM, fixed that.

**Q10. Explain EM here.** Each known fault gives "x failures in n runs". If theta takes one of ten
values with unknown weights, that is a mixture of binomials. E-step: posterior weight of each
value for each fault. M-step: average those weights.

**Q11. Are your parameters identifiable?** With labelled single faults, yes for leak and exposure.
The mixing weights only coarsely, because each fault has 7 to 16 runs. Without labels, no: they
must be transferred from other programs, which is why I test transfer.

### The mutation evidence

**Q12. What is it?** I apply every single edit to each statement, run the tests, and record whether
some variant makes failing tests pass. Five levels, from "no operator applies" to "a variant makes
all tests pass".

**Q13. How does it enter the model?** As a likelihood table: how often each level occurs for faulty
and for fault-free statements, learned on other programs. The ratio multiplies the prior odds.

**Q14. Is that not just mutation-based fault localisation?** The evidence is. What differs is the
combination: a likelihood inside a Bayesian network, instead of a score that is averaged or fed to
a learned ranker. I compare with both.

**Q15. Your 0.96 looks too good.** It is. I inject faults with the same edits I analyse with, so the
exact repair is among the variants for 492 of 594 faults. That is why I report a stress test
without it (0.73) and human-written bugs (0.51, where only 5 of 31 have such a variant).

**Q16. What is the coverage context?** A variant of a statement that a failing test never executes
cannot change that test. So for such statements the mutation evidence is determined by coverage,
and counting it would count coverage twice. I set its likelihood ratio to one.

**Q17. Did that help?** No. It was my hypothesis and it was refuted: without the conditioning the
probabilities are better on all three datasets. I kept the pre-registered model as "proposed" and
report the ablation next to it.

**Q18. Why did it fail?** I do not know for certain. My first explanation was that the benefit
would show with two faults; I tested that on 410 two-fault programs and it did not. What I can say:
with one fault, "not executed by every failing test" proves innocence, and the unconditioned table
encodes that while my generative model only partly does.

**Q19. What happens with two faults?** The fused model gets worse than the model without mutation
evidence: both faults in the top three in 20% of programs against 36%. The tables are learned from
single faults, where "no variant fixes a failing test" means innocent. With a second fault that is
false.

### The evaluation

**Q20. Is your method better than existing ones?** With coverage alone it equals Ochiai and
Barinel. With mutation evidence it equals logistic regression on injected faults and is slightly
behind it in the stress test. On human-written bugs nothing is significant.

**Q21. Then what is the contribution?** A pre-registered comparison of model-based and learned
evidence fusion that includes calibration, abstention and transfer to human-written bugs, with the
finding that the model-based probabilities are more robust on unseen programs, and with three
documented negative results.

**Q22. What is pre-registration and did you keep to it?** I wrote hypotheses, datasets, methods and
comparisons in `research/v3/RESEARCH_PROPOSAL.md` before the code existed. I added one analysis
afterwards, on two faults, and labelled it post hoc. I did not rename the better ablation as my
method.

**Q23. Where does the human-written benchmark come from, and is it "real"?** QuixBugs: 40 classic
algorithms with one-line bugs from a programming challenge; 31 have JSON tests. The bugs were
written by people, not by my mutation operators. They are not bugs from software projects.

**Q24. Only 31 bugs?** Yes. That is why I report intervals and call the result on them a direction,
not a finding.

**Q25. How do you prevent leakage?** Every learned quantity, model parameters, mutation tables,
regression weights and the recalibration map, is fitted without the program under analysis. For
QuixBugs everything comes from my own benchmark. The inference functions take no ground-truth
argument; tests check that.

**Q26. Why is the program the statistical unit?** Mutants of one program share code and tests.
Treating them as independent would make the intervals too narrow.

**Q27. How do you measure calibration?** Brier score, its skill against the base rate, log loss
and ECE with the reliability table, on programs not used for fitting. ECE alone can look good for a
useless predictor, so it is never reported alone.

**Q28. What did recalibration do?** In distribution it nearly removed the miscalibration (ECE 0.045
to 0.005). On human-written bugs the same kind of map made the log loss worse. The same was
reported for code language models by Spiess and co-authors.

**Q29. What is selective localisation?** Answer only when the largest posterior is high. On
injected faults my model's confidence orders its answers better than the gap between the two best
Ochiai scores (area under the risk-coverage curve 0.25 against 0.31, interval excludes zero).

**Q30. Why does logistic regression beat you in places?** It is trained to discriminate, and with
enough matching training data that wins. Under shift it becomes over-confident. This is the classic
trade-off between discriminative and generative models.

### Scope and honesty

**Q31. Where is the language model?** Not evaluated. I had no API access. The code path exists and
its validation logic is tested with a stand-in. The simulated study of version 2 is labelled as
simulated.

**Q32. Why not BugsInPy or Defects4J?** Defects4J is Java. BugsInPy needs a separate environment
per project and programs with thousands of statements, where exact inference is impossible. It is
future work, with approximate inference.

**Q33. What is new?** Not the model. The study design and its findings.

**Q34. Could this be published?** As it stands it is a small, careful empirical study. For a
research venue it would need a real-project benchmark, a state-of-the-art competitor, and a fix for
the multi-fault failure.

**Q35. What is the most serious weakness?** The single-fault assumption of the mutation tables, and
the size of the human-written benchmark.

**Q36. If I move the bug, does the answer move?** Yes; a test does exactly that. In the original
project the answer was always line 4.

**Q37. Show a failure.** `worst_case` in the demonstration for the coverage-only model; section 13
of the experiments for the fused model on two faults.

**Q38. Is 0.582 a probability or a score?** A posterior under the model. Whether it is a good
probability is measured: statements given 0.5 to 0.6 by the coverage-only model are faulty 49% of
the time.

**Q39. Is the repair real?** Each candidate is compiled and run against all tests in a separate
process and the accepted one is re-run. Passing the tests makes a patch plausible, not correct.

**Q40. What would you do next?** Learn mutation tables that do not assume one fault; move to
BugsInPy with approximate inference; collect real LLM confidence.

## Part 7. Honest answers to the failed experiments

| Failed experiment | What to say |
|---|---|
| Coverage-context conditioning | "It was my main modelling idea and the data rejected it. I kept it as the registered model and show the ablation beats it." |
| Size-aware prior | "Mathematically the right base rate, practically irrelevant: better for large programs, worse for small ones." |
| Two faults | "The fused model assumes one fault through its training data. With two it is worse than doing nothing. I would not use it there." |
| Recalibration under shift | "It learns the miscalibration of my benchmark, which is not the miscalibration on other bugs." |
| Dependence slicing (version 2) | "Deleted statements have no dependences, so slicing cannot see them." |
| Static analysis | "pylint never flagged a faulty line. Semantic faults are invisible to it, as they are to a type system." |
| No advantage over Ochiai from coverage alone | "Expected: for single faults good formulas are provably unbeatable on coverage." |
