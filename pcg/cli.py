"""Command line: ``python -m pcg <command>``.

Commands:
    all        benchmark, research experiments, then the demonstration
    benchmark  run the version-2 experiments and write results/benchmark
    research   run the version-3 experiments (fusion, calibration, QuixBugs)
               and write results/research; uses data/external/QuixBugs
    v4         run the version-4 experiments (interventional multi-fault model) and
               write results/v4; uses data/external/QuixBugs and data/external/HumanEvalPack
    v4-synthetic  controlled study on simulated programs; writes results/v4_synthetic
    v4-report  rebuild summary, tables and figures from the raw files in results/v4
    v5         version-5 confirmatory study on fresh MBPP programs; writes results/v5
    v5-report  rebuild summary, tables and figures from the raw files in results/v5
    demo       run the demonstration (needs a finished benchmark run)
    demo-v4    three rule-selected cases for the version-4 model; writes results/demo_v4
    analyze    analyse your own function with your own tests
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import pipeline
from .analysis import analyze
from .execution import oracle_signatures


def _cmd_analyze(args: argparse.Namespace) -> int:
    source = Path(args.source).read_text(encoding="utf-8")
    spec = json.loads(Path(args.tests).read_text(encoding="utf-8"))
    tests = spec["tests"]
    if "expected" in spec:
        expected = ["return:" + repr(value) for value in spec["expected"]]
    elif args.reference:
        expected = oracle_signatures(Path(args.reference).read_text(encoding="utf-8"), args.function, tests)
    else:
        print("error: give expected outputs in the tests file or a --reference implementation", file=sys.stderr)
        return 2
    params = pipeline.load_params(None)
    result = analyze(source, args.function, tests, expected, params, use_static=args.static)
    if result.compile_error is not None:
        d = result.compile_error
        print(f"Compiler diagnostic: {d.kind} at line {d.line}: {d.message}")
        return 1
    print(result.program.listing())
    print(f"\n{result.spectrum.n_failed} of {result.spectrum.n_tests} tests fail.")
    print(f"Parameters: {params.provenance}.")
    print("They were estimated on this project's mutation benchmark and are not validated for other code.\n")
    print(f"P(no fault | evidence) = {result.posterior.p_no_fault:.4f}")
    print(f"{'line':>4}  {'P(faulty)':>9}  statement")
    for line, probability in result.ranking():
        print(f"{line:>4}  {probability:>9.3f}  {result.program.line_text(line).strip()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pcg", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("all", help="benchmark, research, then demo")
    sub.add_parser("benchmark", help="run the version-2 experiments")
    r = sub.add_parser("research", help="run the version-3 experiments")
    r.add_argument("--quixbugs", help="folder with QuixBugs (default: data/external/QuixBugs)")
    sub.add_parser("demo", help="run the demonstration")
    v = sub.add_parser("v4", help="run the version-4 experiments (interventional multi-fault model)")
    v.add_argument("--quixbugs", help="folder with QuixBugs (default: data/external/QuixBugs)")
    v.add_argument("--humaneval", help="HumanEvalPack Python split as JSON lines")
    sub.add_parser("v4-report", help="rebuild summary, tables and figures from results/v4")
    sub.add_parser("v5", help="run the version-5 confirmatory study on MBPP (results/v5)")
    sub.add_parser("v5-report", help="rebuild summary, tables and figures from results/v5")
    sub.add_parser("demo-v4", help="demonstration of the version-4 model on three rule-selected cases")
    sub.add_parser("v4-synthetic", help="controlled study on simulated programs (needs results/v4)")
    p = sub.add_parser("analyze", help="analyse your own function")
    p.add_argument("source", help="Python file containing the function")
    p.add_argument("--function", required=True, help="name of the function under test")
    p.add_argument("--tests", required=True,
                   help='JSON file: {"tests": [[args...], ...], "expected": [value, ...]}')
    p.add_argument("--reference", help="reference implementation to use as oracle instead of 'expected'")
    p.add_argument("--static", action="store_true", help="also use pylint findings as evidence")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return _cmd_analyze(args)
    if args.command in ("all", "benchmark"):
        pipeline.run_benchmark()
    if args.command in ("all", "research"):
        from .research import run_research
        quixbugs = getattr(args, "quixbugs", None)
        run_research(quixbugs_dir=Path(quixbugs) if quixbugs else None)
    if args.command == "v4":
        from .v4 import run_v4
        run_v4(quixbugs_dir=Path(args.quixbugs) if args.quixbugs else None,
               humaneval_file=Path(args.humaneval) if args.humaneval else None)
    if args.command == "v4-synthetic":
        from .synthetic import run_synthetic
        run_synthetic()
    if args.command == "demo-v4":
        from .demo_v4 import run_demo_v4
        run_demo_v4()
    if args.command == "v5":
        from .v5 import run_v5
        run_v5()
    if args.command == "v5-report":
        from . import v5_report
        from .v5 import V5_DIR
        v5_report.write_all(V5_DIR)
    if args.command == "v4-report":
        from . import v4_report
        from .v4 import V4_DIR
        v4_report.write_all(V4_DIR)
    if args.command in ("all", "demo"):
        from .demo import run_demo
        run_demo()
    return 0
