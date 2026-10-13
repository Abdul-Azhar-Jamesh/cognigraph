"""Optional LLM integration (code generation and patch proposals).

Nothing in the benchmark or the demonstration imports this module, so the
project runs without the ``anthropic`` package and without an API key. Calling
these functions sends requests to the Claude API and costs money.

STATUS: the request code below follows the documented SDK shapes but has NOT
been executed against the live API in this project (no credentials were
available). What *is* tested, with a stand-in client, is everything that
decides whether LLM output is trusted: prompt construction, parsing, and the
rule that a proposed patch may only replace lines inside the suspicious region.

Two roles:

* :func:`generate_function`: step 1 of the proposal, "an LLM generates code",
  with a self-reported confidence per line. That confidence is an *uncalibrated
  signal*. It must not be used as a probability; to use it as evidence, collect
  many labelled examples and learn its likelihood with
  ``pcg.estimation.estimate_binned_likelihood`` (see MATHEMATICAL_MODEL.md).
* :func:`make_patch_generator`: a generator for
  ``pcg.repair.repair_with_generator``. Whatever the model proposes is
  validated by compiling and running the whole test suite.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional, Sequence

from .program import Program

DEFAULT_MODEL = os.environ.get("PCG_LLM_MODEL", "claude-opus-5-5")
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "line_confidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"line": {"type": "integer"}, "confidence": {"type": "number"}},
                "required": ["line", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["code", "line_confidence"],
    "additionalProperties": False,
}

PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "replacements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"line": {"type": "integer"}, "new_text": {"type": "string"}},
                "required": ["line", "new_text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["replacements"],
    "additionalProperties": False,
}


class LLMError(RuntimeError):
    """The model call failed or returned something unusable."""


def _default_client() -> Any:
    try:
        import anthropic
    except ImportError as exc:
        raise LLMError("the optional 'anthropic' package is not installed (pip install anthropic)") from exc
    return anthropic.Anthropic()  # credentials come from the environment, never from source code


def _ask_json(client: Any, prompt: str, schema: dict, model: str) -> dict:
    """One request that must come back as JSON matching ``schema``."""
    try:
        import anthropic
        api_errors: tuple = (anthropic.APIStatusError, anthropic.APIConnectionError)
    except ImportError:  # a stand-in client is being used in tests
        api_errors = ()
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=[_FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
    except api_errors as exc:
        raise LLMError(f"API request failed: {type(exc).__name__}: {exc}") from exc
    if response.stop_reason == "refusal":
        raise LLMError("the model declined the request")
    if response.stop_reason == "max_tokens":
        raise LLMError("the response was cut off at max_tokens")
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise LLMError("the response contained no text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError("the response was not valid JSON") from exc


def generation_prompt(specification: str) -> str:
    return (
        "Implement the following Python function. Write one statement per line and no nested functions.\n\n"
        f"{specification}\n\n"
        "Return the complete function as `code`. In `line_confidence`, give for every line of your code "
        "(numbered from 1) a number between 0 and 1: how confident you are that the line is correct."
    )


def generate_function(specification: str, client: Any = None, model: str = DEFAULT_MODEL) -> tuple[str, dict[int, float]]:
    """Ask the model for an implementation and its self-reported line confidence."""
    data = _ask_json(client or _default_client(), generation_prompt(specification), GENERATION_SCHEMA, model)
    confidence = {int(item["line"]): min(1.0, max(0.0, float(item["confidence"]))) for item in data["line_confidence"]}
    return data["code"], confidence


def repair_prompt(
    program: Program,
    region: Sequence[int],
    posteriors: dict[int, float],
    failing_tests: Sequence[dict],
) -> str:
    """Prompt with the code, the failing tests and the uncertainty estimates."""
    suspects = "\n".join(
        f"- line {line}: estimated fault probability {posteriors.get(line, float('nan')):.2f}" for line in region)
    failures = "\n".join(
        f"- {program.func_name}({', '.join(json.dumps(a) for a in t['args'])}): expected {t['expected']}, got {t['observed']}"
        for t in failing_tests)
    return (
        f"This Python function fails some of its tests.\n\n{program.listing()}\n\n"
        f"Failing tests:\n{failures}\n\n"
        "A probabilistic fault-localisation model considers these lines the most suspicious. "
        "The probabilities are estimates and can be wrong:\n"
        f"{suspects}\n\n"
        f"Propose a fix that replaces ONLY lines from this set: {sorted(region)}. "
        "For each line you change, return its number and its complete new text including indentation. "
        "Do not add or remove lines."
    )


def apply_replacements(program: Program, region: Sequence[int], replacements: Sequence[dict]) -> Optional[str]:
    """Splice replacement lines into the program; refuse anything outside the region."""
    lines = program.source.splitlines()
    allowed = set(region)
    if not replacements:
        return None
    for item in replacements:
        line, text = int(item["line"]), str(item["new_text"])
        if line not in allowed or "\n" in text.strip("\n"):
            return None
        lines[line - 1] = text.rstrip("\n")
    return "\n".join(lines) + "\n"


def make_patch_generator(
    posteriors: dict[int, float],
    failing_tests: Sequence[dict],
    client: Any = None,
    model: str = DEFAULT_MODEL,
) -> Callable[[Program, list[int], int], Optional[str]]:
    """Build the ``generate`` callable expected by ``repair_with_generator``."""

    def generate(program: Program, region: list[int], attempt: int) -> Optional[str]:
        nonlocal client
        client = client or _default_client()
        try:
            data = _ask_json(client, repair_prompt(program, region, posteriors, failing_tests), PATCH_SCHEMA, model)
        except LLMError:
            return None
        return apply_replacements(program, region, data.get("replacements", []))

    return generate
