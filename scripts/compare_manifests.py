"""Compare two result manifests: ``python scripts/compare_manifests.py A/MANIFEST.json B/MANIFEST.json``.

Prints how many files are identical and lists the ones that differ (for repeated runs the expected
differences are wall-clock seconds in ``cost.json`` and the files derived from it). Exit status 0 when
the two manifests list the same files and at most the names given with ``--allow`` differ.
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("first")
    parser.add_argument("second")
    parser.add_argument("--allow", nargs="*", default=["cost.json", "summary.json", "SUMMARY.md"],
                        help="file names allowed to differ (default: the timing-dependent ones)")
    args = parser.parse_args()
    a, b = (json.load(open(p, encoding="utf-8"))["files"] for p in (args.first, args.second))
    names = sorted(set(a) | set(b))
    differ = [n for n in names if a.get(n) != b.get(n)]
    print(f"{len(names)} files; identical {len(names) - len(differ)}; differ {differ}")
    unexpected = [n for n in differ if n not in args.allow]
    print("unexpected differences:", unexpected or "none")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
