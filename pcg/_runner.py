"""Child process that executes analysed code and records per-test coverage.

Run as ``python -I _runner.py`` with one JSON job on stdin and one JSON reply
on stdout. It imports only the standard library and never imports ``pcg``, so
analysed code cannot reach the analysis process. This is process isolation
with step and time limits, **not** a security sandbox.

Job:   {"sources": [str], "func": str, "tests": [[arg, ...]], "step_limit": int,
        "expected": [signature] | null, "stop_on_failure": bool}
Reply: {"runs": [{"compile_error": {...} | null, "tests": [test_record, ...]}]}

A test record is {"lines": [int], "exit": "return" | "raise" | "step_limit",
"exit_line": int | null, "signature": str, "value_json": str | null}. The
signature is the observable behaviour of the call: ``return:<repr>`` or
``raise:<ExceptionType>``. A generator result is turned into a list first.
``value_json`` is the returned value as JSON when it can be encoded.
"""

import copy
import json
import re
import sys
import types

TARGET_FILENAME = "<pcg-target>"


_ADDRESS = re.compile(r" at 0x[0-9A-Fa-f]+>")


def stable_repr(value):
    """``repr`` with memory addresses removed.

    The default repr of functions, generators and plain objects contains the
    object's address, which differs from process to process. Behaviour
    signatures must not depend on it.
    """
    return _ADDRESS.sub(" at 0x?>", repr(value))


class StepLimitExceeded(BaseException):
    """Raised inside traced code when the step budget is used up."""


def run_test(func, args, step_limit):
    """Call ``func(*args)`` under a line tracer and describe what happened."""
    lines = set()
    state = {"steps": 0, "depth": 0, "exit_line": None}

    def local_trace(frame, event, arg):
        if event == "line":
            state["steps"] += 1
            if state["steps"] > step_limit:
                raise StepLimitExceeded()
            lines.add(frame.f_lineno)
            if state["depth"] == 1:
                state["exit_line"] = frame.f_lineno
        elif event == "return":
            state["depth"] -= 1
        return local_trace

    def global_trace(frame, event, arg):
        if event == "call" and frame.f_code.co_filename == TARGET_FILENAME:
            state["depth"] += 1
            return local_trace
        return None

    call_args = copy.deepcopy(args)
    value_json = None
    sys.settrace(global_trace)
    try:
        value = func(*call_args)
        if isinstance(value, types.GeneratorType):
            value = list(value)  # run the generator under the tracer; its lines are coverage too
        exit_kind, signature = "return", "return:" + stable_repr(value)
        try:
            value_json = json.dumps(value)
        except (TypeError, ValueError):
            value_json = None
    except StepLimitExceeded:
        exit_kind, signature = "step_limit", "step_limit"
    except BaseException as exc:  # noqa: BLE001 - any failure of analysed code is data
        exit_kind, signature = "raise", "raise:" + type(exc).__name__
    finally:
        sys.settrace(None)
    return {
        "lines": sorted(lines),
        "exit": exit_kind,
        "exit_line": state["exit_line"],
        "signature": signature,
        "value_json": value_json if exit_kind == "return" else None,
    }


def run_source(source, func_name, tests, step_limit, expected, stop_on_failure):
    try:
        code = compile(source, TARGET_FILENAME, "exec")
    except (SyntaxError, ValueError) as exc:
        return {
            "compile_error": {
                "kind": type(exc).__name__,
                "message": getattr(exc, "msg", None) or str(exc),
                "line": getattr(exc, "lineno", None),
                "column": getattr(exc, "offset", None),
            },
            "tests": [],
        }
    namespace = {"__name__": "pcg_target"}
    try:
        exec(code, namespace)  # defines the function; module-level code is trusted to be trivial
        func = namespace[func_name]
    except BaseException as exc:  # noqa: BLE001
        return {
            "compile_error": {
                "kind": "ImportTimeError",
                "message": type(exc).__name__ + ": " + str(exc),
                "line": None,
                "column": None,
            },
            "tests": [],
        }
    records = []
    for index, args in enumerate(tests):
        record = run_test(func, args, step_limit)
        records.append(record)
        if stop_on_failure and expected is not None and record["signature"] != expected[index]:
            break
    return {"compile_error": None, "tests": records}


def main():
    job = json.loads(sys.stdin.read())
    runs = [
        run_source(
            source,
            job["func"],
            job["tests"],
            job["step_limit"],
            job.get("expected"),
            job.get("stop_on_failure", False),
        )
        for source in job["sources"]
    ]
    sys.stdout.write(json.dumps({"runs": runs}))


if __name__ == "__main__":
    main()
