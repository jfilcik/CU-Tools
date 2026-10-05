"""Opt-in native CLI dry-run verification; never performs a paid analysis.

python tools\\cu-experiments\\tests\\verify_public_cli_dry_run.py --cu-executable .venv\\Scripts\\cu.exe
"""

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch
import uuid


TOOL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("experiment", TOOL / "experiment.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cu-executable", required=True)
    arguments = parser.parse_args()
    executable = str(Path(arguments.cu_executable).absolute())
    workspace = TOOL / ".dry-run-work" / uuid.uuid4().hex
    workspace.mkdir(parents=True)
    try:
        source = workspace / "public synthetic file with spaces.txt"
        source.write_text("Synthetic public fixture: Invoice 001, total USD 10.00.\n", encoding="utf-8")
        root = experiment.plan([str(source)], ["prebuilt-document", "prebuilt-layout"],
                               5, 5, str(workspace / "experiment 001"), usage=True)
        _, manifest = experiment.validate_plan(root)
        # Isolate native profile/config lookup to this fixture directory. No credentials
        # or existing user configuration are read, passed, displayed, or serialized.
        env = {key: value for key, value in experiment.cli_environment().items()
               if not key.startswith(("AZURE_", "CU_", "OPENAI_", "MSI_", "IDENTITY_"))}
        home = workspace / "empty-home"
        home.mkdir()
        env.update({"HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home),
                    "LOCALAPPDATA": str(home), "XDG_CONFIG_HOME": str(home),
                    "CU_NO_UPDATE_CHECK": "1", "CU_TELEMETRY": "off"})
        before = {str(p.relative_to(workspace)): p.read_bytes()
                  for p in workspace.rglob("*") if p.is_file()}
        with patch.dict(os.environ, env, clear=True):
            executable, capability = experiment.check_cli(executable, workspace)
        print(capability["version"].strip())
        for batch in manifest["batches"]:
            argv = experiment.analyze_argv(batch, executable, dry_run=True)
            assert "--dry-run" in argv and "--yes" not in argv
            result = subprocess.run(argv, cwd=root, shell=False, env=env,
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=60)
            print(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(f"Native dry-run failed for {batch['id']}: {result.returncode}")
        after = {str(p.relative_to(workspace)): p.read_bytes()
                 for p in workspace.rglob("*") if p.is_file()}
        assert before == after, "Native dry-run unexpectedly wrote or modified files."
        experiment.validate_plan(root)
        print("PASS: two native batches, ten planned submissions, allocations 3+2; no service calls/writes.")
    finally:
        shutil.rmtree(workspace)
        try:
            workspace.parent.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
