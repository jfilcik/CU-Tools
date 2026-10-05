"""Offline experiment planning and bounded official-cu process orchestration.

Use ``python experiment.py plan --help`` or ``python experiment.py run --help``.
No SDK imports, HTTP, per-file scheduling, automatic retries, or analyzer lifecycle.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
from typing import Any


MANIFEST_SCHEMA = "cu-experiments/v1"
REPORT_SCHEMA = "cu-cli/analyze-report/v1"
SCHEMA_LIMITATION = (
    "No source schema snapshots supplied. Analyzer schema identity, model mappings, "
    "and resource identity are not verified; named analyzers/defaults can change."
)
REQUIRED_FLAGS = {
    "--source", "--recursive", "--analyzer", "--json", "--output-dir",
    "--report-file", "--concurrency", "--api-version", "--yes", "--on-existing",
    "--profile", "--usage", "--dry-run",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_path(value: str | Path) -> Path:
    """Reject network paths, streams, links, and junctions, including ancestors."""
    text = os.fspath(value)
    require(bool(text) and "://" not in text and not text.startswith(("\\\\", "//")),
            "Use a regular local path, not a URL or network path.")
    require(not any(ord(c) < 32 for c in text), "Control characters in path.")
    path = Path(os.path.abspath(text))
    require(":" not in str(path)[len(path.drive):], "Alternate file streams are unsupported.")
    for part in (path, *path.parents):
        if os.path.lexists(part):
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not getattr(info, "st_file_attributes", 0) & 0x400,
                    f"Symlinks/reparse points are unsupported: {part}")
    return path


def regular_file(path: Path) -> os.stat_result:
    path = local_path(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode), f"Not a regular file: {path}")
    return info


def fingerprint(path: Path) -> dict[str, Any]:
    regular_file(path)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON constant: {value}")

    regular_file(path)
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=invalid_constant)


def write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    target = path if exclusive else path.with_name(f".{path.name}.pending")
    with target.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        os.replace(target, path)


def file_tree(root: Path) -> set[str]:
    """Inspect directories before descending, never traversing a linked directory."""
    root = local_path(root)
    files = set()
    for directory, folders, names in os.walk(root, followlinks=False):
        for name in folders:
            local_path(Path(directory) / name)
        for name in names:
            path = Path(directory) / name
            regular_file(path)
            files.add(str(path.relative_to(root)))
    return files


def validate_settings(settings: dict) -> None:
    require(type(settings) is dict, "Invalid settings.")
    require(set(settings) == {"analyzers", "iterations", "concurrency",
                              "api_version", "profile", "usage"}, "Invalid settings keys.")
    analyzers = settings["analyzers"]
    require(type(analyzers) is list and bool(analyzers), "Supply at least one analyzer.")
    for analyzer in analyzers:
        require(isinstance(analyzer, str) and bool(re.fullmatch(
            r"(?:[A-Za-z0-9_]{1,64}|prebuilt-[a-z0-9-]{1,55})", analyzer)),
            "Analyzer IDs must be 1-64 letters/digits/underscores, or prebuilt-* IDs.")
    require(len(set(a.casefold() for a in analyzers)) == len(analyzers),
            "Duplicate/colliding analyzer IDs.")
    require(type(settings["iterations"]) is int and settings["iterations"] >= 1,
            "Iterations must be a positive integer.")
    require(type(settings["concurrency"]) is int and 1 <= settings["concurrency"] <= 32,
            "Global concurrency must be 1..32.")
    version = settings["api_version"]
    require(isinstance(version, str) and bool(re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:-preview)?", version)), "Invalid API version.")
    date.fromisoformat(version[:10])
    profile = settings["profile"]
    require(profile is None or (isinstance(profile, str) and bool(re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", profile))), "Invalid profile name.")
    require(type(settings["usage"]) is bool, "Usage must be boolean.")


def validate_input_record(item: dict) -> None:
    require(type(item) is dict and set(item) == {"original", "name", "sha256", "bytes"},
            "Invalid input record.")
    original = item["original"]
    name = item["name"]
    require(isinstance(original, str) and Path(original).is_absolute()
            and "://" not in original and not original.startswith(("\\\\", "//"))
            and not any(ord(c) < 32 for c in original), "Invalid original input path.")
    require(isinstance(name, str) and Path(original).name == name
            and name not in {"", ".", ".."} and not any(c in name for c in '/\\:*?"<>|')
            and not name.startswith(".") and not name.endswith((".", " "))
            and not name.lower().endswith((".result.json", ".result.md")),
            "Input name is unsafe or skipped by native CLI discovery.")
    require(type(item["bytes"]) is int and item["bytes"] >= 0
            and isinstance(item["sha256"], str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", item["sha256"])), "Invalid input hash/size.")


def make_manifest(settings: dict, inputs: list[dict], created: str) -> dict:
    validate_settings(settings)
    require(type(inputs) is list and bool(inputs), "Supply at least one input.")
    for item in inputs:
        validate_input_record(item)
    require(len({os.path.normcase(i["original"]).casefold() for i in inputs}) == len(inputs),
            "Duplicate/colliding inputs.")
    require(isinstance(created, str), "Invalid creation timestamp.")
    datetime.fromisoformat(created)
    count = min(len(settings["analyzers"]), settings["concurrency"])
    base, extra = divmod(settings["concurrency"], count)
    slots = [{"slot": index + 1, "concurrency": base + (index < extra),
              "batches": []} for index in range(count)]
    batches, jobs = [], []
    for index, analyzer in enumerate(settings["analyzers"]):
        batch_id = f"analyzer-{index + 1:04}"
        slot = slots[index % count]
        slot["batches"].append(batch_id)
        directory = Path("batches") / batch_id
        batch = {"id": batch_id, "analyzer": analyzer, "slot": slot["slot"],
                 "concurrency": slot["concurrency"], "source": "inputs",
                 "output_dir": str(directory / "results"),
                 "report_file": str(directory / "native-report.json"),
                 "stdout": str(directory / "stdout.txt"), "stderr": str(directory / "stderr.txt")}
        batch["argv"] = ["cu", "analyze", "--source", batch["source"], "--recursive",
                         "--analyzer", analyzer, "--json", "--output-dir", batch["output_dir"],
                         "--report-file", batch["report_file"], "--concurrency",
                         str(slot["concurrency"]), "--api-version", settings["api_version"],
                         "--yes", "--on-existing", "error"]
        if settings["profile"]:
            batch["argv"] += ["--profile", settings["profile"]]
        if settings["usage"]:
            batch["argv"].append("--usage")
        batches.append(batch)
        for trial in range(1, settings["iterations"] + 1):
            for number, item in enumerate(inputs, 1):
                relative = Path(f"trial-{trial:04}") / f"input-{number:04}" / item["name"]
                jobs.append({"id": f"{batch_id}-trial-{trial:04}-input-{number:04}",
                             "batch": batch_id, "analyzer": analyzer, "trial": trial,
                             "input_number": number, "input": str(Path("inputs") / relative),
                             "output": str(directory / "results" / f"{relative}.result.json"),
                             "sha256": item["sha256"], "bytes": item["bytes"]})
    return {"schema": MANIFEST_SCHEMA, "created_utc": created, "settings": settings,
            "inputs": inputs, "schema_identity": {"validated": False, "limitation": SCHEMA_LIMITATION},
            "native_report_schema": REPORT_SCHEMA, "cli_version": None,
            "cli_version_note": "Plan never invokes cu; run checks and records the executable/version.",
            "total_submissions": len(jobs), "slots": slots, "batches": batches, "jobs": jobs}


def plan(inputs: list[str], analyzers: list[str], iterations: int, concurrency: int,
         output: str, api_version: str = "2025-11-01", profile: str | None = None,
         usage: bool = False) -> Path:
    settings = {"analyzers": analyzers, "iterations": iterations, "concurrency": concurrency,
                "api_version": api_version, "profile": profile, "usage": usage}
    validate_settings(settings)
    root = local_path(output)
    require(not root.exists(), "Output directory already exists; choose a fresh numbered experiment.")
    records, identities = [], set()
    for value in inputs:
        source = local_path(value)
        info = regular_file(source)
        identity = (info.st_dev, info.st_ino) if info.st_ino else str(source).casefold()
        require(identity not in identities, "Duplicate input file (including hard-link aliases).")
        identities.add(identity)
        records.append({"original": str(source), "name": source.name, **fingerprint(source)})
    manifest = make_manifest(settings, records, utc_now())
    root.mkdir(parents=True)
    for job in manifest["jobs"]:
        if job["batch"] != manifest["batches"][0]["id"]:
            continue
        target = root / job["input"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(records[job["input_number"] - 1]["original"], target)
        require(fingerprint(target) == {"sha256": job["sha256"], "bytes": job["bytes"]},
                "Input changed during staging; discard this incomplete plan.")
    write_json(root / "experiment.json", manifest, exclusive=True)
    print(f"Planned {len(manifest['jobs'])} submissions; no service calls. Experiment: {root}")
    return root


def validate_plan(directory: str | Path) -> tuple[Path, dict]:
    root = local_path(directory)
    require(root.is_dir(), "Experiment directory is missing.")
    require(not (root / "run.json").exists(), "Already attempted; never resume/rebill. Make a new plan.")
    manifest = strict_json(root / "experiment.json")
    require(type(manifest) is dict, "Invalid manifest.")
    try:
        expected = make_manifest(manifest["settings"], manifest["inputs"], manifest["created_utc"])
    except (KeyError, TypeError) as exc:
        raise ValueError("Malformed experiment manifest.") from exc
    require(manifest == expected, "Manifest matrix, commands, allocation, or metadata was modified.")
    staged = {j["input"]: j for j in manifest["jobs"]}
    require(file_tree(root) == {"experiment.json", *staged},
            "Unexpected or missing files; experiments must be pristine before run.")
    for relative, job in staged.items():
        path = root / relative
        require(regular_file(path).st_nlink == 1, "Staged files must be independent copies.")
        require(fingerprint(path) == {"sha256": job["sha256"], "bytes": job["bytes"]},
                f"Staged input hash/size mismatch: {relative}")
    return root, manifest


def cli_environment() -> dict[str, str]:
    return {**os.environ, "CU_NO_UPDATE_CHECK": "1", "NO_COLOR": "1", "COLUMNS": "160"}


def check_cli(executable: str, cwd: Path) -> tuple[str, dict]:
    resolved = shutil.which(executable)
    require(resolved is not None, "Official cu not found. Install/upgrade public PyPI cu-cli "
            "and select its executable with --cu-executable.")
    resolved = str(Path(resolved).absolute())
    require(Path(resolved).suffix.lower() not in {".bat", ".cmd"},
            "Select the cu executable, not a shell/batch wrapper.")
    evidence = {}
    for name, arguments in (("version", ["--version"]), ("help", ["analyze", "--help"])):
        result = subprocess.run([resolved, *arguments], cwd=cwd, shell=False,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30, env=cli_environment())
        require(result.returncode == 0, "Unable to check official cu capabilities. Install/upgrade "
                "public PyPI cu-cli and use --cu-executable.")
        evidence[name] = result.stdout + result.stderr
    require(bool(re.search(r"\bcu, version \S+", evidence["version"]))
            and REQUIRED_FLAGS <= set(re.findall(r"--[a-z][a-z-]+", evidence["help"])),
            "Incompatible cu CLI. Install/upgrade public PyPI cu-cli; use --cu-executable. "
            "This helper does not translate legacy flags.")
    return resolved, evidence


def analyze_argv(batch: dict, executable: str, *, dry_run: bool = False) -> list[str]:
    argv = [executable, *batch["argv"][1:]]
    if dry_run:
        argv.remove("--yes")
        argv.append("--dry-run")
    return argv


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def report_path(root: Path, value: Any) -> str:
    require(isinstance(value, str) and bool(value), "Missing native input/output path.")
    require("://" not in value and not value.startswith(("\\\\", "//"))
            and not any(ord(c) < 32 for c in value), "Invalid native report path.")
    path = Path(os.path.abspath(root / value))
    require(path.is_relative_to(root), "Native report path escapes experiment.")
    return os.path.normcase(str(path))


def validate_payload(payload: Any, analyzer: str) -> None:
    require(type(payload) is dict, "Malformed native result (expected object).")
    content = payload
    if "result" in payload:
        require("contents" not in payload and isinstance(payload.get("status"), str)
                and payload["status"].lower() == "succeeded",
                "Native LRO envelope must have succeeded status and an unambiguous result.")
        content = payload["result"]
    require(type(content) is dict and type(content.get("contents")) is list
            and all(type(c) is dict for c in content["contents"]),
            "Malformed analyzer result (expected contents or result.contents array).")
    for level in (payload, content):
        require(not level.get("error") and not level.get("errors")
                and isinstance(level.get("status", "succeeded"), str)
                and level.get("status", "succeeded").lower() == "succeeded"
                and level.get("analyzerId", analyzer) == analyzer,
                "Service error/non-success or mismatched analyzer in result payload.")
    require(not any(c.get("error") or c.get("errors") for c in content["contents"]),
            "Service error in content entry.")


def reconcile(root: Path, batch: dict, jobs: list[dict], exit_code: int | None) -> dict:
    """Trust only matching native entries AND intact full-result JSON, never console text."""
    outcomes = [{"id": j["id"], "input": j["input"], "output": j["output"],
                 "status": "inconclusive", "usage": None, "cost": None,
                 "service_latency_seconds": None} for j in jobs]
    errors = []
    result = {"id": batch["id"], "analyzer": batch["analyzer"], "exit_code": exit_code,
              "status": "inconclusive", "errors": errors, "jobs": outcomes}
    try:
        report = strict_json(root / batch["report_file"])
        require(type(report) is dict and report.get("schema") == REPORT_SCHEMA
                and report.get("analyzer") == batch["analyzer"]
                and report.get("result_view") == "full", "Unexpected native report contract.")
        entries = report.get("results")
        require(type(entries) is list, "Malformed native report results.")
        counts = {status: 0 for status in ("succeeded", "failed", "skipped")}
        by_input = {}
        expected = {report_path(root, j["input"]) for j in jobs}
        for entry in entries:
            require(type(entry) is dict and entry.get("status") in counts
                    and entry.get("analyzer") == batch["analyzer"], "Malformed native report entry.")
            key = report_path(root, entry.get("input"))
            require(key in expected and key not in by_input, "Duplicate/unexpected native input.")
            by_input[key] = entry
            counts[entry["status"]] += 1
        counts["total"] = len(entries)
        require(report.get("counts") == counts and all(
            type(v) is int for v in report["counts"].values()), "Native report counts mismatch.")
        actual_outputs = file_tree(root / batch["output_dir"])
        expected_outputs = {str(Path(j["output"]).relative_to(batch["output_dir"])) for j in jobs}
        require(actual_outputs <= expected_outputs, "Unexpected native output files.")
        for job, outcome in zip(jobs, outcomes):
            entry = by_input.get(report_path(root, job["input"]))
            try:
                require(entry is not None, "Missing native report entry.")
                if entry["status"] != "succeeded":
                    outcome["status"] = "failed" if entry["status"] == "failed" else "inconclusive"
                    raise ValueError(f"Native status: {entry['status']}; see native report.")
                require(not entry.get("error"), "Success entry also contains an error.")
                require(report_path(root, entry.get("output")) == report_path(root, job["output"]),
                        "Native output does not match planned job.")
                payload = strict_json(root / job["output"])
                validate_payload(payload, batch["analyzer"])
                outcome["result_sha256"] = fingerprint(root / job["output"])["sha256"]
                outcome["status"] = "succeeded"
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                outcome["reason"] = str(exc)
                errors.append(f"{job['id']}: {exc}")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc))
    if exit_code != 0:
        errors.append(f"CLI exit code {exit_code}; successful jobs cannot be confirmed.")
        for outcome in outcomes:
            if outcome["status"] == "succeeded":
                outcome["status"] = "inconclusive"
    statuses = {o["status"] for o in outcomes}
    result["status"] = ("succeeded" if not errors and statuses == {"succeeded"}
                        else "failed" if "failed" in statuses or exit_code not in (0, None)
                        else "inconclusive")
    return result


def run(directory: str, confirm_cost: bool = False, cu_executable: str = "cu") -> int:
    require(confirm_cost, "No service calls made. Run requires --confirm-cost for all planned submissions.")
    root, manifest = validate_plan(directory)
    executable, capabilities = check_cli(cu_executable, root)
    # Recheck after preflight and claim the experiment exclusively before any paid command.
    validate_plan(root)
    print(f"Confirmed budget: {manifest['total_submissions']} submissions; global concurrency "
          f"{manifest['settings']['concurrency']}. No automatic retry/resume.", flush=True)
    batches = {b["id"]: b for b in manifest["batches"]}
    state = {"schema": "cu-experiments/run/v1", "status": "running", "started_utc": utc_now(),
             "total_submissions": manifest["total_submissions"], "slots": manifest["slots"],
             "executable": executable, "cli_capabilities": capabilities, "usage": None, "cost": None,
             "batches": {b: {"id": b, "status": "not-run", "exit_code": None,
                             "jobs": [{"id": j["id"], "status": "not-run"}
                                      for j in manifest["jobs"] if j["batch"] == b]}
                         for b in batches}}
    lock, stopping = threading.Lock(), threading.Event()
    processes: set[subprocess.Popen] = set()

    def persist() -> None:
        state["completed_batches"] = sum(b["status"] in {"succeeded", "failed", "inconclusive"}
                                         for b in state["batches"].values())
        write_json(root / "run.json", state)

    def worker(slot: dict) -> None:
        for batch_id in slot["batches"]:
            batch = batches[batch_id]
            argv = analyze_argv(batch, executable)
            with lock:
                if stopping.is_set():
                    return
                state["batches"][batch_id]["status"] = "running"
                state["batches"][batch_id]["argv"] = argv
                persist()
            code, failure = None, None
            try:
                (root / batch["report_file"]).parent.mkdir(parents=True, exist_ok=True)
                with (root / batch["stdout"]).open("xb") as stdout, (
                        root / batch["stderr"]).open("xb") as stderr:
                    with lock:
                        if stopping.is_set():
                            return
                        process = subprocess.Popen(argv, cwd=root, shell=False,
                                                   stdin=subprocess.DEVNULL, stdout=stdout,
                                                   stderr=stderr, env=cli_environment())
                        processes.add(process)
                    try:
                        code = process.wait()
                    except BaseException:
                        stop_process(process)
                        raise
                    finally:
                        with lock:
                            processes.discard(process)
            except Exception as exc:
                failure = f"CLI process failed: {exc}"
            outcome = reconcile(root, batch, [j for j in manifest["jobs"] if j["batch"] == batch_id], code)
            outcome["argv"] = argv
            if failure:
                outcome["errors"].append(failure)
            with lock:
                state["batches"][batch_id] = outcome
                persist()

    def terminate_children() -> None:
        with lock:
            stopping.set()
            children = list(processes)
        for child in children:
            stop_process(child)

    def interrupted(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    pool = None
    old_signal = None
    write_json(root / "run.json", state, exclusive=True)
    try:
        if threading.current_thread() is threading.main_thread():
            old_signal = signal.signal(signal.SIGTERM, interrupted)
        pool = ThreadPoolExecutor(max_workers=len(manifest["slots"]))
        futures = [pool.submit(worker, slot) for slot in manifest["slots"]]
        for future in as_completed(futures):
            future.result()
        statuses = {b["status"] for b in state["batches"].values()}
        state["status"] = ("succeeded" if statuses == {"succeeded"} else
                           "failed" if "failed" in statuses else "inconclusive")
    except (KeyboardInterrupt, Exception) as exc:
        state["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "inconclusive"
        state["error"] = f"{type(exc).__name__}: {exc}"
        terminate_children()
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
        if old_signal is not None:
            signal.signal(signal.SIGTERM, old_signal)
        state["finished_utc"] = utc_now()
        with lock:
            for batch in state["batches"].values():
                if batch["status"] == "running":
                    batch["status"] = "inconclusive"
            persist()
    print(f"Experiment {state['status']}: {root / 'run.json'}")
    return 0 if state["status"] == "succeeded" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan", help="Freeze explicit files; no CLI/auth/service calls.")
    planner.add_argument("--input", action="append", required=True, dest="inputs")
    planner.add_argument("--analyzer", action="append", required=True, dest="analyzers")
    planner.add_argument("--iterations", type=int, required=True)
    planner.add_argument("--concurrency", type=int, default=5, help="Global request budget, 1..32.")
    planner.add_argument("--output", required=True)
    planner.add_argument("--api-version", default="2025-11-01")
    planner.add_argument("--profile")
    planner.add_argument("--usage", action="store_true", help="Preserve CLI usage text; no token parsing.")
    runner = commands.add_parser("run", help="Execute a fresh plan once through official cu.")
    runner.add_argument("directory")
    runner.add_argument("--confirm-cost", action="store_true")
    runner.add_argument("--cu-executable", default="cu", help="Official cu executable, not a shell command.")
    arguments = vars(parser.parse_args(argv))
    command = arguments.pop("command")
    try:
        if command == "plan":
            plan(**arguments)
            return 0
        return run(**arguments)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted. Keep evidence; never rerun a partially attempted experiment.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
