# Legacy LLM sample (record only)

These two files are the only LLM output that existed in the original project:

* `llm_generation_output.txt`: the saved reply for `has_close_elements` (code plus a confidence per line).
* `llm_confidence.json`: the confidence values parsed from it.

Provenance is uncertain. The text has a uniform three-space indent, which suggests it was pasted from
a chat window; it could not be confirmed that the original `generate.py` produced it.

Nothing in the `pcg` package reads these files. Six confidence values for one correct function are far
too few to estimate how informative an LLM's confidence is, so they are kept only as a record.
