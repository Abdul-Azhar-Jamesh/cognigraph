"""Static-analysis evidence from pylint (real analyser output, parsed as JSON).

A finding becomes the binary evidence variable ``A_i = 1`` for the statement on
its line only if it is potentially about behaviour (pylint types ``error``,
``fatal``, ``warning``, minus a short list of layout warnings). Convention and
refactoring messages are style advice: they are recorded but never used as
evidence about correctness. How informative ``A_i`` is, is not assumed: its
likelihoods are estimated from labelled data in ``pcg.estimation``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import config


class StaticAnalysisError(RuntimeError):
    """pylint is missing or did not return parseable output."""


@dataclass(frozen=True)
class Finding:
    """One pylint message."""

    line: int
    type: str
    symbol: str
    message: str

    @property
    def relevant(self) -> bool:
        """True when the finding may concern behaviour rather than style."""
        return self.type in config.STATIC_RELEVANT_TYPES and self.symbol not in config.STATIC_IGNORED_SYMBOLS

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "type": self.type,
            "symbol": self.symbol,
            "message": self.message,
            "relevant": self.relevant,
        }


def run_pylint(sources: Sequence[str], timeout: float = 900.0) -> list[list[Finding]]:
    """Run pylint once over all ``sources``; return the findings for each.

    The sources are written to a temporary directory, so the user's files are
    never touched. Raises :class:`StaticAnalysisError` instead of returning an
    empty result when pylint cannot be run: a missing analyser must not look
    like "no findings".
    """
    if not sources:
        return []
    with tempfile.TemporaryDirectory(prefix="pcg_pylint_") as tmp:
        names = []
        for index, source in enumerate(sources):
            name = f"pcg_src_{index:05d}"
            (Path(tmp) / f"{name}.py").write_text(source, encoding="utf-8")
            names.append(name)
        command = [
            sys.executable, "-m", "pylint",
            "--output-format=json", "--score=n", "--persistent=n", "--jobs=1",
            "--disable=duplicate-code",
            *[f"{name}.py" for name in names],
        ]
        try:
            proc = subprocess.run(
                command, cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise StaticAnalysisError("pylint timed out") from exc
    # pylint's exit status is a bit mask of message categories; 32 means usage error.
    if proc.returncode & 32 or "No module named pylint" in proc.stderr:
        raise StaticAnalysisError(f"pylint could not run: {proc.stderr.strip()[-400:]}")
    try:
        messages = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise StaticAnalysisError("pylint output is not valid JSON") from exc

    by_name: dict[str, list[Finding]] = {name: [] for name in names}
    for message in messages:
        module = str(message.get("module", ""))
        if module in by_name:
            by_name[module].append(
                Finding(int(message["line"]), message["type"], message["symbol"], message["message"])
            )
    return [sorted(by_name[name], key=lambda f: (f.line, f.symbol)) for name in names]


def flagged_lines(findings: Sequence[Finding]) -> frozenset[int]:
    """Lines that carry at least one correctness-relevant finding."""
    return frozenset(f.line for f in findings if f.relevant)
