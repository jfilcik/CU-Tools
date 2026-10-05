"""Offline tests: python -m unittest discover -s tools\\cu-experiments\\tests -v."""

from contextlib import redirect_stdout, redirect_stderr
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid


TOOL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("experiment", TOOL / "experiment.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        # All test files stay in the owned project directory, never OS temp storage.
        self.workspace = TOOL / ".test-work" / uuid.uuid4().hex
        self.workspace.mkdir(parents=True)
        self.source = self.workspace / "sample with spaces & punctuation.pdf"
        self.source.write_bytes(b"%PDF-1.4\nsynthetic offline test\n%%EOF\n")
        self.root = self.workspace / "experiment 001"
        self.output = io.StringIO()
        self.quiet = redirect_stdout(self.output)
        self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None, None, None)
        shutil.rmtree(self.workspace)
        try:
            self.workspace.parent.rmdir()
        except OSError:
            pass

    def plan(self, analyzers=None, iterations=2, concurrency=5, **kwargs):
        return experiment.plan([str(self.source)], analyzers or ["test_v1"], iterations,
                               concurrency, str(self.root), **kwargs)

    def manifest(self):
        return experiment.strict_json(self.root / "experiment.json")

    def native(self, root, batch, jobs, *, statuses=None, code=0, envelope=False):
        entries = []
        counts = {"succeeded": 0, "failed": 0, "skipped": 0, "total": len(jobs)}
        for index, job in enumerate(jobs):
            status = statuses[index] if statuses else "succeeded"
            entry = {"input": str(root / job["input"]), "analyzer": batch["analyzer"],
                     "status": status}
            counts[status] += 1
            if status == "succeeded":
                entry["output"] = str(root / job["output"])
                output = root / job["output"]
                output.parent.mkdir(parents=True, exist_ok=True)
                if envelope:
                    output.write_text(json.dumps({
                        "id": "synthetic-operation-id", "status": "Succeeded",
                        "result": {"analyzerId": batch["analyzer"], "apiVersion": "2025-11-01",
                                   "createdAt": "2026-09-16T00:00:00Z", "stringEncoding": "utf16",
                                   "warnings": [], "contents": [{"fields": {}}]},
                        "usage": {"documentPagesStandard": 1}
                    }, indent=2) + "\n", encoding="utf-8")
                else:
                    output.write_bytes(b'{\n "contents": [{"fields": {}}]\n}\n')
            entries.append(entry)
        report = {"schema": experiment.REPORT_SCHEMA, "analyzer": batch["analyzer"],
                  "result_view": "full", "counts": counts, "results": entries}
        destination = root / batch["report_file"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        experiment.write_json(destination, report)
        return report

    def test_plan_cardinality_frozen_copies_and_unique_outputs(self):
        second = self.workspace / "other" / self.source.name
        second.parent.mkdir()
        second.write_bytes(b"different public test bytes")
        with patch.object(experiment.subprocess, "run", side_effect=AssertionError("No CLI in plan")), (
                patch.object(experiment.subprocess, "Popen", side_effect=AssertionError("No CLI in plan"))):
            experiment.plan([str(self.source), str(second)], ["test_v1", "test_v2"],
                            10, 10, str(self.root))
        manifest = self.manifest()
        self.assertEqual(40, manifest["total_submissions"])
        self.assertEqual(40, len({job["output"] for job in manifest["jobs"]}))
        staged = {job["input"] for job in manifest["jobs"]}
        self.assertEqual(20, len(staged))
        self.assertEqual(20, len({(self.root / name).stat().st_ino for name in staged}))
        self.source.write_bytes(b"later source edit")
        experiment.validate_plan(self.root)
        self.assertFalse(manifest["schema_identity"]["validated"])
        self.assertIsNone(manifest["cli_version"])

    def test_budgets_and_assignments(self):
        for count, budget in ((1, 10), (2, 5), (3, 10), (10, 3), (40, 32)):
            settings = {"analyzers": [f"a_{i}" for i in range(count)], "iterations": 1,
                        "concurrency": budget, "api_version": "2025-11-01",
                        "profile": None, "usage": False}
            record = {"original": str(self.source), "name": self.source.name,
                      **experiment.fingerprint(self.source)}
            manifest = experiment.make_manifest(settings, [record], experiment.utc_now())
            self.assertEqual(budget, sum(s["concurrency"] for s in manifest["slots"]))
            self.assertEqual(min(count, budget), len(manifest["slots"]))
            self.assertEqual(count, len({b for s in manifest["slots"] for b in s["batches"]}))
            for batch in manifest["batches"]:
                self.assertEqual(str(batch["concurrency"]),
                                 batch["argv"][batch["argv"].index("--concurrency") + 1])

    def test_invalid_inputs_counts_ids_and_existing_directory(self):
        for key, value in (("iterations", 0), ("iterations", -1), ("concurrency", 0),
                           ("concurrency", 33), ("analyzers", ["bad/id"]),
                           ("analyzers", ["same", "SAME"]), ("api_version", "2025-13-01"),
                           ("profile", "https://example.invalid/key")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.plan(**{key: value})
        for inputs in ([str(self.source), str(self.source)], [str(self.workspace)],
                       ["https://example.invalid/a.pdf"], [str(self.workspace / "missing.pdf")]):
            with self.subTest(inputs=inputs), self.assertRaises((ValueError, OSError)):
                experiment.plan(inputs, ["a"], 1, 1, str(self.root))
        self.root.mkdir()
        with self.assertRaises(ValueError):
            self.plan()

    def test_native_discovery_skipped_names_are_rejected(self):
        for name in (".hidden.pdf", "prior.result.json", "prior.result.md"):
            path = self.workspace / name
            path.write_bytes(b"test")
            with self.subTest(name=name), self.assertRaises(ValueError):
                experiment.plan([str(path)], ["a"], 1, 1, str(self.root))

    def test_hard_link_alias_is_duplicate_and_staged_link_rejected(self):
        alias = self.workspace / "alias.pdf"
        os.link(self.source, alias)
        with self.assertRaises(ValueError):
            experiment.plan([str(self.source), str(alias)], ["a"], 1, 1, str(self.root))
        self.plan()
        staged = self.root / self.manifest()["jobs"][0]["input"]
        staged.unlink()
        os.link(self.source, staged)
        with self.assertRaisesRegex(ValueError, "independent copies"):
            experiment.validate_plan(self.root)

    def test_symlinks_and_linked_parents_rejected(self):
        linked = self.workspace / "linked.pdf"
        try:
            linked.symlink_to(self.source)
        except OSError:
            self.skipTest("This account cannot create symlinks.")
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            experiment.plan([str(linked)], ["a"], 1, 1, str(self.root))
        linked_parent = self.workspace / "linked-parent"
        linked_parent.symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            experiment.local_path(linked_parent / self.source.name)

    def test_link_reparse_and_nonregular_checks_without_symlink_privileges(self):
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFREG, 0x400)):
            with self.subTest(mode=mode, attributes=attributes), patch.object(
                    Path, "lstat", return_value=SimpleNamespace(
                        st_mode=mode, st_file_attributes=attributes)):
                with self.assertRaisesRegex(ValueError, "Symlinks/reparse"):
                    experiment.local_path(self.source)
        with patch.object(experiment, "local_path", return_value=self.source), (
                patch.object(Path, "stat", return_value=SimpleNamespace(st_mode=stat.S_IFIFO))):
            with self.assertRaisesRegex(ValueError, "Not a regular file"):
                experiment.regular_file(self.source)

    def test_manifest_matrix_argv_allocation_and_snapshot_tampering(self):
        self.plan(["a", "b"], iterations=3)
        original = self.manifest()
        for modify in (
                lambda m: m["jobs"].pop(),
                lambda m: m["jobs"][0].update(output="..\\escape.result.json"),
                lambda m: m["batches"][0]["argv"].append("--api-key"),
                lambda m: m["slots"][0].update(concurrency=32),
                lambda m: m.update(total_submissions=0)):
            changed = copy.deepcopy(original)
            modify(changed)
            experiment.write_json(self.root / "experiment.json", changed)
            with self.assertRaises(ValueError):
                experiment.validate_plan(self.root)
        experiment.write_json(self.root / "experiment.json", original)
        extra = self.root / "inputs" / "unplanned.pdf"
        extra.write_bytes(b"must not be submitted")
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            experiment.validate_plan(self.root)
        extra.unlink()
        staged = self.root / original["jobs"][0]["input"]
        staged.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash/size"):
            experiment.validate_plan(self.root)

    def test_missing_confirmation_never_calls_cli(self):
        self.plan()
        with patch.object(experiment, "check_cli", side_effect=AssertionError("No preflight")), (
                patch.object(experiment.subprocess, "Popen", side_effect=AssertionError("No run"))):
            with self.assertRaisesRegex(ValueError, "confirm-cost"):
                experiment.run(str(self.root))
        self.assertFalse((self.root / "run.json").exists())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, experiment.main(["run", str(self.root)]))

    def test_cli_capability_check_uses_only_local_argument_arrays(self):
        self.plan()
        help_text = " ".join(experiment.REQUIRED_FLAGS)
        responses = [subprocess.CompletedProcess([], 0, "cu, version 0.1.0b1", ""),
                     subprocess.CompletedProcess([], 0, help_text, "")]
        with patch.object(experiment.shutil, "which", return_value=str(self.source.with_suffix(".exe"))), (
                patch.object(experiment.subprocess, "run", side_effect=responses)) as native:
            _, evidence = experiment.check_cli("cu", self.root)
        self.assertIn("0.1.0b1", evidence["version"])
        for call in native.call_args_list:
            self.assertIsInstance(call.args[0], list)
            self.assertFalse(call.kwargs["shell"])
        self.assertEqual(["--version"], native.call_args_list[0].args[0][1:])
        self.assertEqual(["analyze", "--help"], native.call_args_list[1].args[0][1:])
        self.assertFalse((self.root / "run.json").exists())

    def test_unsupported_cli_refuses_before_running_marker(self):
        self.plan()
        with patch.object(experiment.shutil, "which", return_value="old-cu.exe"), (
                patch.object(experiment.subprocess, "run",
                             return_value=subprocess.CompletedProcess([], 0, "old cu --input", ""))):
            with self.assertRaisesRegex(ValueError, "Incompatible cu"):
                experiment.run(str(self.root), True)
        self.assertFalse((self.root / "run.json").exists())

    def test_cli_failure_and_missing_executable(self):
        with patch.object(experiment.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "Install/upgrade"):
                experiment.check_cli("missing", self.workspace)
        with patch.object(experiment.shutil, "which", return_value="cu.exe"), (
                patch.object(experiment.subprocess, "run",
                             return_value=subprocess.CompletedProcess([], 2, "", "error"))):
            with self.assertRaisesRegex(ValueError, "Install/upgrade"):
                experiment.check_cli("cu", self.workspace)

    def test_native_reconciliation_and_untouched_bytes(self):
        self.plan()
        manifest = self.manifest()
        batch = manifest["batches"][0]
        self.native(self.root, batch, manifest["jobs"])
        before = [(self.root / j["output"]).read_bytes() for j in manifest["jobs"]]
        report = experiment.reconcile(self.root, batch, manifest["jobs"], 0)
        self.assertEqual("succeeded", report["status"])
        self.assertEqual(["succeeded"] * 2, [j["status"] for j in report["jobs"]])
        self.assertIsNone(report["jobs"][0]["usage"])
        self.assertIsNone(report["jobs"][0]["service_latency_seconds"])
        self.assertEqual(before, [(self.root / j["output"]).read_bytes() for j in manifest["jobs"]])

    def test_native_relative_report_paths_and_skipped_entries(self):
        self.plan()
        manifest = self.manifest()
        batch, jobs = manifest["batches"][0], manifest["jobs"]
        native = self.native(self.root, batch, jobs)
        for entry, job in zip(native["results"], jobs):
            entry.update(input=job["input"], output=job["output"])
        experiment.write_json(self.root / batch["report_file"], native)
        self.assertEqual("succeeded", experiment.reconcile(self.root, batch, jobs, 0)["status"])
        self.native(self.root, batch, jobs, statuses=["skipped", "succeeded"])
        report = experiment.reconcile(self.root, batch, jobs, 0)
        self.assertEqual("inconclusive", report["status"])
        self.assertEqual("inconclusive", report["jobs"][0]["status"])

    def test_native_lro_envelope_preserves_raw_result_and_page_usage(self):
        self.plan()
        manifest = self.manifest()
        batch, jobs = manifest["batches"][0], manifest["jobs"]
        self.native(self.root, batch, jobs, envelope=True)
        before = [(self.root / j["output"]).read_bytes() for j in jobs]
        report = experiment.reconcile(self.root, batch, jobs, 0)
        self.assertEqual("succeeded", report["status"])
        self.assertEqual(before, [(self.root / j["output"]).read_bytes() for j in jobs])
        for raw, outcome in zip(before, report["jobs"]):
            self.assertEqual({"documentPagesStandard": 1}, json.loads(raw)["usage"])
            self.assertIsNone(outcome["usage"])
            self.assertIsNone(outcome["cost"])

    def test_native_lro_envelope_rejects_non_success_and_invalid_nested_payload(self):
        self.plan()
        manifest = self.manifest()
        batch, jobs = manifest["batches"][0], manifest["jobs"]
        output = self.root / jobs[0]["output"]
        for modify in (
                lambda p: p.update(status="Failed"),
                lambda p: p.update(status="Running"),
                lambda p: p.update(status=None),
                lambda p: p.pop("status"),
                lambda p: p.update(result=None),
                lambda p: p.update(result=[]),
                lambda p: p.update(result={}),
                lambda p: p.update(contents=[]),
                lambda p: p.update(error={"code": "failed"}),
                lambda p: p["result"].update(error={"code": "failed"}),
                lambda p: p["result"].update(status="failed"),
                lambda p: p["result"].update(analyzerId="wrong_analyzer"),
                lambda p: p["result"].update(contents=[{"error": {"code": "failed"}}])):
            self.native(self.root, batch, jobs, envelope=True)
            payload = experiment.strict_json(output)
            modify(payload)
            experiment.write_json(output, payload)
            report = experiment.reconcile(self.root, batch, jobs, 0)
            self.assertEqual("inconclusive", report["status"])
            self.assertEqual("inconclusive", report["jobs"][0]["status"])

    def test_partial_failure_and_nonzero_exit_are_not_success(self):
        self.plan()
        manifest = self.manifest()
        batch, jobs = manifest["batches"][0], manifest["jobs"]
        self.native(self.root, batch, jobs, statuses=["succeeded", "failed"])
        report = experiment.reconcile(self.root, batch, jobs, 0)
        self.assertEqual("failed", report["status"])
        self.assertEqual(["succeeded", "failed"], [j["status"] for j in report["jobs"]])
        report = experiment.reconcile(self.root, batch, jobs, 1)
        self.assertEqual(["inconclusive", "failed"], [j["status"] for j in report["jobs"]])
        self.native(self.root, batch, jobs)
        report = experiment.reconcile(self.root, batch, jobs, 9)
        self.assertEqual("failed", report["status"])
        self.assertTrue(all(j["status"] != "succeeded" for j in report["jobs"]))

    def test_missing_malformed_duplicate_unexpected_native_reports(self):
        self.plan()
        manifest = self.manifest()
        batch, jobs = manifest["batches"][0], manifest["jobs"]
        native_path = self.root / batch["report_file"]
        for mode in ("missing", "bad-json", "bad-schema", "bad-counts", "duplicate",
                     "unexpected", "bad-entry", "wrong-analyzer", "wrong-output", "missing-entry"):
            report = self.native(self.root, batch, jobs)
            if mode == "missing":
                native_path.unlink()
            elif mode == "bad-json":
                native_path.write_text('{"results": ', encoding="utf-8")
            else:
                if mode == "bad-schema":
                    report["schema"] = "unknown/v2"
                elif mode == "bad-counts":
                    report["counts"]["total"] = 999
                elif mode == "duplicate":
                    report["results"][1] = report["results"][0]
                elif mode == "unexpected":
                    report["results"][0]["input"] = str(self.source)
                elif mode == "bad-entry":
                    report["results"][0] = None
                elif mode == "wrong-analyzer":
                    report["analyzer"] = "somebody_else"
                elif mode == "wrong-output":
                    report["results"][0]["output"] = report["results"][1]["output"]
                elif mode == "missing-entry":
                    report["results"].pop()
                    report["counts"].update(total=1, succeeded=1)
                experiment.write_json(native_path, report)
            with self.subTest(mode=mode):
                result = experiment.reconcile(self.root, batch, jobs, 0)
                self.assertNotEqual("succeeded", result["status"])
                self.assertTrue(result["errors"])
                self.assertTrue(any(j["status"] != "succeeded" for j in result["jobs"]))

    def test_missing_malformed_service_error_and_unexpected_output(self):
        self.plan()
        manifest = self.manifest()
        batch, jobs = manifest["batches"][0], manifest["jobs"]
        output = self.root / jobs[0]["output"]
        for payload in (None, b"{broken", b"[]", b"{}", b'{"contents":null}',
                        b'{"contents":[],"status":"failed"}',
                        b'{"contents":[],"analyzerId":"wrong_analyzer"}',
                        b'{"contents":[],"error":{"code":"failed"}}',
                        b'{"contents":[{"error":{"code":"failed"}}]}',
                        b'{"contents":[],"contents":[]}', b'{"contents":[],"x":NaN}'):
            self.native(self.root, batch, jobs)
            if payload is None:
                output.unlink()
            else:
                output.write_bytes(payload)
            with self.subTest(payload=payload):
                report = experiment.reconcile(self.root, batch, jobs, 0)
                self.assertEqual("inconclusive", report["status"])
                self.assertNotEqual("succeeded", report["jobs"][0]["status"])
        self.native(self.root, batch, jobs)
        (output.parent / "extra.result.json").write_text("{}", encoding="utf-8")
        report = experiment.reconcile(self.root, batch, jobs, 0)
        self.assertTrue(all(j["status"] != "succeeded" for j in report["jobs"]))

    def fake_process(self, *, returncode=0, fail_launch=False, started=None, envelope=False):
        owner = self
        active = {"budget": 0, "maximum": 0, "calls": [], "processes": []}
        lock = threading.Lock()

        class FakeProcess:
            def __init__(self, argv, **kwargs):
                if fail_launch:
                    raise OSError("synthetic launch failure")
                self.argv = argv
                self.kwargs = kwargs
                self.returncode = None
                self.stopped = threading.Event()
                self.terminated = False
                self.budget = int(argv[argv.index("--concurrency") + 1])
                self.cwd = Path(kwargs["cwd"])
                self.manifest = experiment.strict_json(self.cwd / "experiment.json")
                owner.assertEqual("running", experiment.strict_json(self.cwd / "run.json")["status"])
                owner.assertFalse(kwargs["shell"])
                owner.assertEqual("analyze", argv[1])
                with lock:
                    active["budget"] += self.budget
                    active["maximum"] = max(active["maximum"], active["budget"])
                    active["calls"].append(argv)
                    active["processes"].append(self)
                if started is not None:
                    started.set()

            def wait(self, timeout=None):
                if self.returncode is not None:
                    return self.returncode
                if started is not None:
                    self.stopped.wait(3)
                else:
                    time.sleep(0.015)
                if self.returncode is None:
                    analyzer = self.argv[self.argv.index("--analyzer") + 1]
                    batch = next(b for b in self.manifest["batches"] if b["analyzer"] == analyzer)
                    jobs = [j for j in self.manifest["jobs"] if j["batch"] == batch["id"]]
                    owner.native(self.cwd, batch, jobs, envelope=envelope)
                    self.kwargs["stdout"].write(b"raw stdout\n")
                    self.kwargs["stderr"].write(b"usage evidence, not a machine token schema\n")
                    self.returncode = returncode
                    with lock:
                        active["budget"] -= self.budget
                return self.returncode

            def poll(self):
                return self.returncode

            def terminate(self):
                self.terminated = True
                self.returncode = -15
                self.stopped.set()

            def kill(self):
                self.terminate()

        return FakeProcess, active

    def test_complete_run_cli_only_global_budget_persistence_and_rerun_prevention(self):
        self.plan(["a", "b", "c", "d", "e"], iterations=5, concurrency=3, usage=True, profile="demo")
        original = (self.root / "experiment.json").read_bytes()
        fake, active = self.fake_process()
        executable = str(self.workspace / "CLI path with spaces" / "cu.exe")
        with patch.object(experiment, "check_cli", return_value=(executable, {"version": "test"})), (
                patch.object(experiment.subprocess, "Popen", side_effect=fake)):
            self.assertEqual(0, experiment.run(str(self.root), True, executable))
            with self.assertRaisesRegex(ValueError, "Already attempted"):
                experiment.run(str(self.root), True, executable)
        self.assertEqual(original, (self.root / "experiment.json").read_bytes())
        self.assertEqual(5, len(active["calls"]))
        self.assertLessEqual(active["maximum"], 3)
        self.assertGreaterEqual(active["maximum"], 2)
        report = experiment.strict_json(self.root / "run.json")
        self.assertEqual("succeeded", report["status"])
        self.assertEqual(5, report["completed_batches"])
        self.assertEqual(25, report["total_submissions"])
        for batch in report["batches"].values():
            self.assertEqual(executable, batch["argv"][0])
            self.assertIn("--usage", batch["argv"])
            self.assertIn("--yes", batch["argv"])
            self.assertEqual(5, len(batch["jobs"]))
            self.assertNotIn("--input", batch["argv"])
        for batch in self.manifest()["batches"]:
            self.assertEqual(b"raw stdout\n", (self.root / batch["stdout"]).read_bytes())
            self.assertIn(b"usage evidence", (self.root / batch["stderr"]).read_bytes())

    def test_launch_failure_and_failed_run_are_permanently_blocked(self):
        self.plan()
        fake, _ = self.fake_process(fail_launch=True)
        with patch.object(experiment, "check_cli", return_value=("cu.exe", {})), (
                patch.object(experiment.subprocess, "Popen", side_effect=fake)):
            self.assertEqual(1, experiment.run(str(self.root), True))
        self.assertEqual("inconclusive", experiment.strict_json(self.root / "run.json")["status"])
        with self.assertRaisesRegex(ValueError, "Already attempted"):
            experiment.run(str(self.root), True)

    def test_nonzero_cli_is_overall_failure(self):
        self.plan()
        fake, _ = self.fake_process(returncode=7)
        with patch.object(experiment, "check_cli", return_value=("cu.exe", {})), (
                patch.object(experiment.subprocess, "Popen", side_effect=fake)):
            self.assertEqual(1, experiment.run(str(self.root), True))
        self.assertEqual("failed", experiment.strict_json(self.root / "run.json")["status"])

    def test_complete_run_accepts_native_lro_results(self):
        self.plan(["a", "b"], iterations=2, concurrency=2)
        fake, _ = self.fake_process(envelope=True)
        with patch.object(experiment, "check_cli", return_value=("cu.exe", {})), (
                patch.object(experiment.subprocess, "Popen", side_effect=fake)):
            self.assertEqual(0, experiment.run(str(self.root), True))
        self.assertEqual("succeeded", experiment.strict_json(self.root / "run.json")["status"])

    def test_interruption_terminates_started_children_preserves_evidence(self):
        self.plan(["a", "b", "c"], iterations=2, concurrency=1)
        started = threading.Event()
        fake, active = self.fake_process(started=started)

        def interrupt(_futures):
            self.assertTrue(started.wait(3))
            raise KeyboardInterrupt("synthetic interruption")

        with patch.object(experiment, "check_cli", return_value=("cu.exe", {})), (
                patch.object(experiment.subprocess, "Popen", side_effect=fake)), (
                patch.object(experiment, "as_completed", side_effect=interrupt)):
            self.assertEqual(1, experiment.run(str(self.root), True))
        self.assertEqual(1, len(active["processes"]))
        self.assertTrue(active["processes"][0].terminated)
        report = experiment.strict_json(self.root / "run.json")
        self.assertEqual("interrupted", report["status"])
        self.assertEqual(2, sum(b["status"] == "not-run" for b in report["batches"].values()))
        self.assertTrue((self.root / self.manifest()["batches"][0]["stderr"]).exists())
        with self.assertRaisesRegex(ValueError, "Already attempted"):
            experiment.validate_plan(self.root)

    def test_existing_running_state_rejected(self):
        self.plan()
        experiment.write_json(self.root / "run.json", {"status": "running"}, exclusive=True)
        with patch.object(experiment, "check_cli", side_effect=AssertionError("No CLI")):
            with self.assertRaisesRegex(ValueError, "Already attempted"):
                experiment.run(str(self.root), True)

    def test_wait_failure_stops_process_before_next_analyzer(self):
        self.plan(["a", "b"], concurrency=1)
        fake, active = self.fake_process()
        original_wait = fake.wait

        def failing_wait(process, timeout=None):
            if timeout is None and process.returncode is None:
                raise OSError("synthetic wait failure")
            return original_wait(process, timeout)

        with patch.object(experiment, "check_cli", return_value=("cu.exe", {})), (
                patch.object(experiment.subprocess, "Popen", side_effect=fake)), (
                patch.object(fake, "wait", failing_wait)):
            self.assertEqual(1, experiment.run(str(self.root), True))
        self.assertEqual(2, len(active["processes"]))
        self.assertTrue(all(p.terminated for p in active["processes"]))

    def test_json_manifest_errors_are_actionable(self):
        self.plan()
        for text in ("null", "[]", "{}", '{"schema":1,"schema":2}', '{"settings":null}'):
            (self.root / "experiment.json").write_text(text, encoding="utf-8")
            with self.subTest(text=text), redirect_stderr(io.StringIO()):
                self.assertEqual(2, experiment.main(["run", str(self.root), "--confirm-cost"]))


if __name__ == "__main__":
    unittest.main()
