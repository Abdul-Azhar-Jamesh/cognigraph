# Audit of the original project (before the rebuild)

Date of audit: 2026-10-13. The original project is preserved unchanged in
`archive/original-third-party-backup/` (47 files, verified identical by `diff -r` before anything was
changed). Every finding below was checked by reading the code and, where possible, by running it
in an isolated copy. Commands and outputs are in [BASELINE_RESULTS.md](BASELINE_RESULTS.md).

## What the original project was

Thirteen stand-alone scripts that passed data to each other through fixed file names:

| Script | What it did |
|---|---|
| `generate.py` | Asked an LLM for code plus a self-reported confidence per line |
| `parse_output.py` | Split the reply into `generated_code.py` and `confidence.json` |
| `build_graph.py` | Turned the AST into a networkx graph of statements |
| `evidence_execution.py` | Ran 7 test cases and wrote a score per line |
| `evidence_static.py` | Ran pylint and wrote a penalty per line |
| `bayesian_fusion.py` | `sigmoid(logit(confidence) + 2*exec + 2*static)` per line |
| `visualize_graph.py` | Drew the graph |
| `repair.py` | Wrote a prompt into a text file |
| `review_function.py`, `score_function.py`, `rank_codebase.py` | Ranked functions by the minimum line score |

No report, no dataset, no dependency file and no git history were present.

## Findings and their status

| ID | Finding in the earlier audit | Status | Evidence |
|---|---|---|---|
| D1 | The faulty line is hardcoded | **Confirmed** | `evidence_execution.py` lines 28-30: if any test fails, every line gets -0.3 and `execution_evidence["4"] = -1.0`. Injecting bugs on lines 3, 5 and 6 instead of line 4 produced the identical output: line 4 = 0.72, flagged `[4]` |
| D2 | Fusion constants are arbitrary, not likelihood ratios | **Confirmed** | `bayesian_fusion.py` lines 24 and 27 multiply hand-typed scores by 2.0. No likelihood is defined or estimated anywhere in the repository |
| D3 | The graph is not used by inference | **Confirmed** | `bayesian_fusion.py` reads three JSON files and never opens `pcg_graph.gml`. The graph is read only by `visualize_graph.py` |
| D4 | The ranking is the LLM's opinion | **Confirmed** | With every hand-pasted LLM confidence set to 0.9, the three sample functions tie at 0.8578 |
| D5 | The evaluation is one function with one bug | **Confirmed** | The only experiments are `has_close_elements` (one bug) and three sample functions (one bug) |
| D6 | Style warnings lower the "probability of correctness" | **Confirmed** | A missing docstring costs -0.2; re-parsing the saved LLM output produced `bad-indentation` warnings that lowered every line |
| D7 | There is no repair loop | **Confirmed** | `repair.py` only writes `repair_prompt.txt`. `repaired_code.py` is byte-identical to `generated_code.py` |
| D8 | Shipped outputs come from different states | **Confirmed** | `posterior.json` matches the buggy `>` code, `pcg_graph_final.gml` and the PNG match the mis-indented correct code, and `generated_code.py` is a hand-cleaned correct version. Running the documented steps on the shipped folder gives "Nothing to repair" |
| D9 | The 0.75 threshold is tuned to the demo | **Confirmed** | Changing the LLM confidence of line 4 from 0.95 to 0.97 gives 0.814 and nothing is flagged |
| D10 | Stale score files are reused after a failure | **Confirmed by inspection, not executed** | `rank_codebase.py` `try_score` ignores the subprocess result and loads any existing `_score.json` |
| D11 | `pr.py` is unrelated and wrong | **Confirmed** | A burglary-alarm network whose variables are sampled independently, so the learned `P(Alarm | B=1, E=1)` is 0.5 from zero observations |

No finding of the earlier audit turned out to be incorrect.

## Additional observations made during this pass

* The README claimed four evidence sources. Compiler diagnostics did not exist in the code; `mypy`
  was listed as a dependency and never used; `pytest` and `coverage.py` were named as the execution
  evidence but `evidence_execution.py` used neither. The stray `.coverage` file was recorded on
  another machine (`C:\Users\Deepak\pcg-project`).
* Graph node identifiers contained memory addresses (`line_4_2634107810256`), so the graph changed
  on every run.
* The saved LLM output has a uniform three-space indent on every line, which suggests it was pasted
  from a chat window rather than produced by `generate.py`. **Unverified.**
* The headline claim "despite the LLM itself being confident" was misleading: the LLM's 0.95 was
  given to the correct `<` line. The bug was typed in afterwards, so the LLM never saw it.

## What was kept

| Kept | Where it lives now |
|---|---|
| The idea: fuse several evidence sources into a per-statement fault probability | The whole project |
| The `has_close_elements` example and its 7 test inputs | `pcg/benchmark_programs.py` (first program, extended to 12 tests) |
| The buggy `get_max` sample | `max_of_list` in the benchmark |
| The AST statement walker | Rewritten as `pcg/program.py::body_statements` |
| pylint JSON parsing | `pcg/static_analysis.py` |
| The one real sample of LLM output | `data/legacy/` (kept as a record; not used by any computation) |

## What was removed and why

Everything else: the hardcoded evidence script, the magic-constant fusion, the prompt-only repair
script, the manual copy-paste ranking pipeline, `pr.py`, all stale output files and the duplicated
`reviews/` and `sample_code/` folders. All of it remains available in the backup folder.
