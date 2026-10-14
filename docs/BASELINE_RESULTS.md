# Baseline: what the original project produced

All commands were run on 2026-10-13 in an isolated copy of the original project, never in the
project folder itself. To repeat them, copy `archive/original-third-party-backup/` somewhere and run
them there.

## Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home 10.0.26200 |
| Python | 3.12.3 |
| Present on the system | networkx 3.5, matplotlib 3.10.5, numpy 2.2.5, pandas 2.2.3, pytest 9.1.1, pgmpy 1.1.2 |
| Missing on the system | pylint, coverage, mypy, anthropic |
| Installed into a throw-away virtual environment for the baseline | pylint 4.1.3, coverage |

`generate.py` was **not executed**: it needs the `anthropic` package and a paid API key.
Everything else was executed.

## 1. The project's own test

```
python -m pytest -q test_problem.py      ->  1 passed
```

The single test checks the example function. No test checks any of the mathematics.

## 2. Documented pipeline on the shipped files

```
python evidence_execution.py   ->  Passed: 7, Failed: 0
                                   {'1': 1.0, '2': 1.0, '3': 1.0, '4': 1.0, '5': 1.0, '6': 1.0}
python evidence_static.py      ->  {'1': -0.2, '2': -0.1, '3': 0.0, '4': 0.0, '5': 0.0, '6': -0.1}
python bayesian_fusion.py      ->  0.9895, 0.982, 0.9852, 0.9929, 0.9852, 0.9914
python repair.py               ->  Flagged low-confidence lines: []   Nothing to repair.
```

The shipped `generated_code.py` is correct, so the documented steps show no bug. The shipped
`posterior.json` (0.8748, 0.8017, 0.8316, 0.72, 0.8316, 0.8951) cannot be reproduced from the
shipped source without editing it by hand.

## 3. Reproducing the README's headline number

Replacing `<` by `>` on line 4 by hand and re-running:

```
Passed: 4, Failed: 3
Line 1: 0.8748  Line 2: 0.8017  Line 3: 0.8316  Line 4: 0.72  Line 5: 0.8316  Line 6: 0.8951
Flagged low-confidence lines: [4]
```

The number 0.72 reproduces. Arithmetic check: `sigmoid(logit(0.95) - 2) = sigmoid(0.944) = 0.72`,
where 0.95 is the LLM's confidence and -2 is the hardcoded `-1.0 * 2.0`.

## 4. Counterexamples: move the bug, keep the answer

Starting again from the correct code each time and injecting one different bug:

| Injected bug | Tests passed / failed | Posterior of line 4 | Lines flagged |
|---|---|---|---|
| line 4: `<` to `>` (the README's bug) | 4 / 3 | 0.72 | `[4]` |
| line 6: `return False` to `return True` | 4 / 3 | 0.72 | `[4]` |
| line 3: `range(i + 1, ...)` to `range(i, ...)` | 4 / 3 | 0.72 | `[4]` |
| line 5: `return True` to `return False` | 3 / 4 | 0.72 | `[4]` |

All six posteriors are identical in the four runs. The output does not depend on where the bug is.

## 5. Fragility of the threshold

Same bug as the README, LLM confidence of line 4 changed from 0.95 to 0.97:

```
Line 4: 0.814      Flagged low-confidence lines: []
```

## 6. Where the shipped graph came from

Running `parse_output.py` on the shipped `generation_output.txt` writes code with a 7-space
indent. pylint then reports `bad-indentation` on every line, and fusion gives 0.9733, 0.9781,
0.9895, 0.9781, 0.9872 for lines 2-6. These are exactly the values stored in the shipped
`pcg_graph_final.gml`. The shipped picture therefore shows a correct program penalised for
whitespace, not the bug demonstration.

## 7. Ranking pipeline

```
python rank_codebase.py sample_code
1  utils__get_max       0.3531
2  utils__is_even       0.9559
3  utils__add_numbers   0.9705
```

Reproduces the README table. After setting every hand-pasted LLM confidence to 0.9:

```
1  utils__add_numbers   0.8578
2  utils__is_even       0.8578
3  utils__get_max       0.8578
```

The buggy function is no longer distinguishable. The whole ranking came from the pasted number 0.4.

## 8. `pr.py`

Ran with pgmpy 1.1.2. Variables are sampled independently, so the fitted table for
`Alarm` given `Burglary = 1, Earthquake = 1` is 0.5 / 0.5 from zero observations, and
`P(JohnCalls = 1 | Alarm)` is about 0.05 in both columns. Unrelated to this project.

## Baseline in one sentence

The original system reported the same answer for four different bugs, so it has no measurable
fault-localisation ability; the rebuilt system is evaluated from scratch in
[EXPERIMENTS.md](EXPERIMENTS.md).
