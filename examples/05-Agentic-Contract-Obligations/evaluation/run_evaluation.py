"""Build the contract dataset, run EvalLens, and generate the accuracy report."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent


def _run(command: list[str], cwd: Path) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def _latest_result(run_id: str) -> Path:
    result_dir = HERE / "output" / "local_results" / run_id
    matches = sorted(result_dir.glob("contract_obligations_*.json"))
    if not matches:
        raise FileNotFoundError(f"No EvalLens result found under {result_dir}")
    return matches[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--run-id", default="contract_obligations_v1")
    parser.add_argument(
        "--evallens-root",
        type=Path,
        default=Path(os.getenv("EVALLENS_ROOT", r"C:\src\EvalLens")),
        help="Local EvalLens checkout for development; install EvalLens to omit this override.",
    )
    args = parser.parse_args()

    _run(
        [
            sys.executable,
            str(PROJECT_DIR / "scripts" / "build_evallens_dataset.py"),
            "--results",
            str(args.results.resolve()),
        ],
        PROJECT_DIR,
    )
    env_pythonpath = os.environ.get("PYTHONPATH", "")
    if args.evallens_root.exists():
        os.environ["PYTHONPATH"] = (
            str(args.evallens_root.resolve())
            + os.pathsep
            + env_pythonpath
        )
    _run(
        [
            sys.executable,
            "-m",
            "evallens",
            "run",
            "--run-id",
            args.run_id,
            "--config",
            "config.yml",
        ],
        HERE,
    )
    result_path = _latest_result(args.run_id)
    _run(
        [
            sys.executable,
            str(HERE / "generate_accuracy_report.py"),
            "--input",
            str(result_path),
        ],
        HERE,
    )


if __name__ == "__main__":
    main()
