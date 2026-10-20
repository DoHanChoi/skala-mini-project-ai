"""Run the current test harness against archived baseline code, without checkout.

Usage from the repository root: ./.venv/bin/python tests/run_pinned_baseline.py
Requires the baseline commit in local Git history; never fetches from the network.
"""
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main():
    """로컬 기준 소스를 임시 추출해 같은 테스트를 실행하고 종료 코드를 반환한다."""
    root = Path(__file__).resolve().parent.parent
    fixture = json.loads((root / "tests/fixtures/diagnosis_cases.json").read_text(encoding="utf-8"))
    baseline = fixture["baseline_commit"]
    archive = subprocess.run(
        ["git", "archive", baseline, "agent", "server.py", "data"],
        cwd=root, check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="skala-baseline-") as directory:
        target = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(target, filter="data")
        shutil.copytree(root / "tests", target / "tests",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"Baseline commit: {baseline}", flush=True)
        # Same interpreter and fixture, separate source directory and temp DBs.
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=target)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
