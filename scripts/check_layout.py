"""Lightweight checks of the project layout: ``python scripts/check_layout.py``.

1. every module of the ``pcg`` package imports;
2. the data and result paths used by ``pcg.config`` exist;
3. every ``results/*/MANIFEST.json`` still matches the files next to it (same hashing rule as
   ``pcg.experiments.OutputDir.finish``: line endings normalised for text files);
4. every relative link in the Markdown documents resolves;
5. every figure listed in ``figures/README.md`` exists;
6. the archive checksums verify (only if ``archive/SHA256SUMS.txt`` exists; use ``--no-archive`` to skip).

Exit status 0 when everything passes. Nothing is written.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import pkgutil
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TEXT_SUFFIXES = {".json", ".jsonl", ".csv", ".md", ".txt", ".py"}
SKIP_DIRS = {".git", ".venv", "archive", "__pycache__"}
failures: list[str] = []


def report(ok: bool, message: str) -> None:
    print(("ok    " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


def check_imports() -> None:
    import pcg

    names = [m.name for m in pkgutil.iter_modules(pcg.__path__)]
    bad = []
    for name in names:
        try:
            importlib.import_module(f"pcg.{name}")
        except Exception as exc:  # noqa: BLE001 - report any import problem
            bad.append(f"{name}: {exc}")
    report(not bad, f"{len(names)} modules import" + (f" ({'; '.join(bad)})" if bad else ""))


def check_paths() -> None:
    from pcg import config

    for name in ("PROJECT_ROOT", "RESULTS_DIR", "QUIXBUGS_DIR", "HUMANEVALPACK_FILE"):
        path = getattr(config, name)
        report(Path(path).exists(), f"config.{name} -> {Path(path).relative_to(ROOT) if ROOT in Path(path).parents else path}")
    report(Path(config.PROJECT_ROOT).resolve() == ROOT, "config.PROJECT_ROOT is this project folder")


def file_hash(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def check_manifests() -> None:
    for manifest in sorted((ROOT / "results").glob("*/MANIFEST.json")):
        folder = manifest.parent
        recorded = json.loads(manifest.read_text(encoding="utf-8")).get("files", {})
        actual = {f.relative_to(folder).as_posix(): file_hash(f)
                  for f in sorted(folder.rglob("*")) if f.is_file() and f.name != "MANIFEST.json"}
        missing = sorted(set(recorded) - set(actual))
        extra = sorted(set(actual) - set(recorded))
        changed = sorted(k for k in recorded if k in actual and recorded[k] != actual[k])
        detail = ""
        if missing or extra or changed:
            detail = f" (missing {missing[:3]}, extra {extra[:3]}, changed {changed[:3]})"
        report(not (missing or extra or changed), f"results/{folder.name}: {len(recorded)} files match MANIFEST.json{detail}")


def markdown_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.md")
            if not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and "data/external" not in p.relative_to(ROOT).as_posix()]


def check_links() -> None:
    link = re.compile(r"\]\(([^)\s]+)\)")
    broken, total = [], 0
    for md in markdown_files():
        text = re.sub(r"```.*?```", "", md.read_text(encoding="utf-8"), flags=re.S)
        for target in link.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            total += 1
            path = target.split("#")[0].split(":")[0] if not re.match(r"^[A-Za-z]:", target) else target
            if path and not (md.parent / path).exists():
                broken.append(f"{md.relative_to(ROOT).as_posix()} -> {target}")
    report(not broken, f"{total} relative links in {len(markdown_files())} documents resolve" + (f"; broken: {broken[:8]}" if broken else ""))


def check_figures() -> None:
    index = ROOT / "figures" / "README.md"
    if not index.exists():
        report(False, "figures/README.md exists")
        return
    listed = re.findall(r"`(results/[^`]+\.(?:png|pdf))`", index.read_text(encoding="utf-8"))
    missing = [p for p in listed if not (ROOT / p).exists()]
    report(bool(listed) and not missing, f"{len(listed)} figures listed in figures/README.md exist" + (f"; missing {missing[:5]}" if missing else ""))


def check_archive() -> None:
    sums = ROOT / "archive" / "SHA256SUMS.txt"
    if not sums.exists():
        print("skip  archive checksums (no archive/SHA256SUMS.txt)")
        return
    bad = 0
    lines = [ln for ln in sums.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for line in lines:
        digest, name = line.split(None, 1)
        path = ROOT / "archive" / name.strip().lstrip("*")
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            bad += 1
    report(bad == 0, f"archive: {len(lines)} files verify against SHA256SUMS.txt")


if __name__ == "__main__":
    check_imports()
    check_paths()
    check_manifests()
    check_links()
    check_figures()
    if "--no-archive" not in sys.argv:
        check_archive()
    print("\nALL CHECKS PASSED" if not failures else f"\n{len(failures)} CHECK(S) FAILED")
    sys.exit(1 if failures else 0)
