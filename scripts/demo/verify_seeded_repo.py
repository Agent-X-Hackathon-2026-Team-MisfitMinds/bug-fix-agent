"""Prove the seeded demo repo is demo-ready (T-17 acceptance).

Checks, on a throwaway copy so the real repo is never modified:
  1. the existing suite is green with the seeded bugs present;
  2. for each bug: the reference test fails before the known fix,
     and the reference test plus the whole suite pass after it.

Run from the repository root:  python scripts/demo/verify_seeded_repo.py
Exit code 0 means every check passed.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEEDED = ROOT / "seeded-demo-repo"
REFERENCE = Path(__file__).resolve().parent / "reference"

# issue number -> (buggy line, fixed line) in src/app.py
KNOWN_FIXES = {
    1: ("    return price - discount + 1\n", "    return price - discount\n"),
    2: ("    if age < 18 or age >= 65:\n", "    if age < 18 or age > 65:\n"),
    3: (
        "    user = _lookup_user(user_id)\n",
        "    user = _lookup_user(user_id)\n    if user is None:\n        return None\n",
    ),
}


def pytest_passes(repo: Path, *targets: str) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True).returncode == 0


def fresh_copy(tmp: Path, name: str) -> Path:
    repo = tmp / name
    shutil.copytree(SEEDED, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return repo


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool) -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            failures.append(label)

    with tempfile.TemporaryDirectory(prefix="seeded-verify-") as tmp_name:
        tmp = Path(tmp_name)
        check("baseline suite is green with bugs present", pytest_passes(fresh_copy(tmp, "base")))

        for issue, (buggy, fixed) in KNOWN_FIXES.items():
            repo = fresh_copy(tmp, f"issue{issue}")
            test_name = f"test_issue_{issue}.py"
            shutil.copy(REFERENCE / test_name, repo / "tests" / test_name)
            target = f"tests/{test_name}"

            check(f"issue {issue}: reference test fails before fix (red)",
                  not pytest_passes(repo, target))

            app = repo / "src" / "app.py"
            source = app.read_text(encoding="utf-8")
            check(f"issue {issue}: buggy line found exactly once", source.count(buggy) == 1)
            app.write_text(source.replace(buggy, fixed), encoding="utf-8")

            check(f"issue {issue}: reference test passes after fix (green)",
                  pytest_passes(repo, target))
            check(f"issue {issue}: full suite green after fix", pytest_passes(repo))

    print(f"\n{len(failures)} failed" if failures else "\nall checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
