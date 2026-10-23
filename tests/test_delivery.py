"""Observable installer and acceptance invariants; no network or application services."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/delivery/scripts/delivery.py"
spec = importlib.util.spec_from_file_location("delivery", SCRIPT)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / "README.md").write_text("Run the sample locally.\n", encoding="utf-8")

    def start(self):
        d.initialize(self.root)
        d.new_run(self.root, "sample", "Sample delivery")
        self.plan, self.record_path = d.run_paths(self.root, "sample")
        self.record = d.read_json(self.record_path)
        self.record["scope"] = "One local feature; hosted deployment is a separate followup."
        self.record["tasks"] = [{"id": "T01", "title": "Local feature", "paths": ["src.py"],
            "depends_on": [], "state": "READY", "repairs": 0, "used_minutes": 0,
            "checks": [self.check_def("C1")]}]
        self.record["overall"]["checks"] = [self.check_def("C2")]
        self.save()

    @staticmethod
    def check_def(cid):
        return {"id": cid, "kind": "REQUIRED", "method": "local sample check",
                "expected": "Sample behavior matches the scope"}

    def save(self):
        self.record_path.write_bytes(d.packed(self.record))

    def approve(self, task_ids=None):
        self.save()
        baseline = d.guard(self.root, "sample")["baseline"]
        self.record["approval"] = {"decision": "APPROVED", "reviewer": "Fixture reviewer",
            "at": "2026-10-22T10:00:00+08:00", "source": "Isolated test fixture approval",
            **baseline, "tasks": task_ids or ["T01"], "paths": ["src.py"],
            "operations": ["edit", "test"], "limits": {"max_repairs": 3, "max_minutes": 60}}
        self.save()

    def evidence(self, cid, result="PASS"):
        report = self.root / f"report-{cid}.txt"
        report.write_text(f"{cid}: actual local result {result}\n", encoding="utf-8")
        self.record["evidence"].append({"id": f"E{len(self.record['evidence'])+1}", "check": cid,
            "baseline": d.guard(self.root, "sample")["baseline"],
            "method": "local sample check", "actual": f"Fixture observed {result}",
            "result": result, "at": "2026-10-22T10:05:00+08:00", "producer": "test fixture",
            "report": {"path": report.name, "sha256": d.digest(report.read_bytes())},
            "subjects": [{"path": "src.py", "sha256": d.digest((self.root / 'src.py').read_bytes())}]})
        self.save()

    def complete(self):
        self.start()
        self.approve()
        self.finish_task("T01")
        self.accept()

    def start_two_tasks(self):
        self.start()
        second = copy.deepcopy(self.record["tasks"][0])
        second.update({"id": "T02", "title": "Second local feature", "state": "PENDING",
                       "depends_on": ["T01"], "checks": [self.check_def("C3")]})
        self.record["tasks"].append(second)
        self.save()

    def finish_task(self, tid):
        task = next(t for t in self.record["tasks"] if t["id"] == tid)
        for check in task["checks"]:
            self.evidence(check["id"])
        task["state"] = "DONE"
        self.save()

    def accept(self):
        self.evidence("C2")
        self.record["overall"].update({"accepted_by": "Fixture receiver",
            "accepted_at": "2026-10-22T10:10:00+08:00", "source": "Fixture acceptance"})
        self.record["handoff"].update({"artifacts": ["src.py"], "docs": ["README.md"],
            "knowledge": {"status": "NO_INCREMENT", "reason": "Sample README already sufficient"}})
        self.save()

    def complete_two_batches(self):
        self.start_two_tasks()
        self.approve(["T01"])
        self.finish_task("T01")
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.approve(["T02"])
        self.finish_task("T02")
        self.accept()

    def codes(self, result):
        return {x["code"] for x in result["issues"]}

    def test_inspection_is_read_only_bounded_and_excludes_dependencies(self):
        hidden = self.root / "node_modules/pkg"
        hidden.mkdir(parents=True)
        (hidden / "package.json").write_text("{}")
        (self.root / "package.json").write_text("{}")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = d.inspect(self.root)
        self.assertIn("package.json", result["candidates"])
        self.assertNotIn("node_modules/pkg/package.json", result["candidates"])
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_init_is_idempotent_and_preserves_project_rules_and_config(self):
        rules = b"# Team rules\r\nKeep these bytes.\r\n"
        (self.root / "AGENTS.md").write_bytes(rules)
        d.initialize(self.root)
        config_path = self.root / ".delivery/project.json"
        config = d.read_json(config_path)
        config["commands"] = {"test": {"command": "python -m unittest", "status": "NOT_VERIFIED"}}
        config_path.write_bytes(d.packed(config))
        result = d.initialize(self.root)
        self.assertEqual(result["written"], 0)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), rules)
        self.assertEqual(d.read_json(config_path), config)
        self.assertEqual(d.check(self.root)["status"], "CONFIGURED")
        self.assertIsNone(config["policy"]["max_repairs"])

    def test_local_edit_aborts_install_before_other_writes(self):
        d.initialize(self.root)
        installed = self.root / ".agents/skills/delivery"
        (installed / "SKILL.md").write_text("My local edit", encoding="utf-8")
        missing = installed / "references/planning.md"
        missing.unlink()
        with self.assertRaisesRegex(ValueError, "Local edit/conflict"):
            d.initialize(self.root)
        self.assertFalse(missing.exists())
        self.assertEqual((installed / "SKILL.md").read_text(), "My local edit")

    def test_static_check_does_not_run_project_commands(self):
        d.initialize(self.root)
        path = self.root / ".delivery/project.json"
        config = d.read_json(path)
        config["commands"] = {"test": {"command": "THIS_MUST_NEVER_EXECUTE"}}
        path.write_bytes(d.packed(config))
        result = d.check(self.root)
        self.assertEqual(result["status"], "CONFIGURED")
        self.assertFalse(result["runtime_verified"])

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        for path in ("../outside", "/tmp/outside", "C:/outside", "..\\outside", "a/../b", "a//b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                d.safe(self.root, path)

    def test_file_in_managed_parent_aborts_without_partial_install(self):
        parent = self.root / ".agents/skills/delivery"
        parent.mkdir(parents=True)
        (parent / "references").write_text("Preserve this local file", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a directory"):
            d.initialize(self.root)
        self.assertFalse((parent / "SKILL.md").exists())
        self.assertFalse((self.root / ".delivery/project.json").exists())

    def test_linked_managed_path_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        try:
            os.symlink(outside, self.root / ".delivery", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Host does not permit directory symlinks: {exc}")
        with self.assertRaises(ValueError):
            d.initialize(self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_new_run_has_no_approval_and_never_overwrites(self):
        d.initialize(self.root)
        d.new_run(self.root, "sample", "Sample delivery")
        plan, record = d.run_paths(self.root, "sample")
        before = (plan.read_bytes(), record.read_bytes())
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["delivery_ready"])
        with self.assertRaises(ValueError):
            d.new_run(self.root, "sample", "Overwrite")
        self.assertEqual(before, (plan.read_bytes(), record.read_bytes()))

    def test_approval_is_required_for_execution(self):
        self.start()
        self.assertFalse(d.guard(self.root, "sample")["execution_ready"])
        self.approve()
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])

    def test_plan_change_invalidates_approval(self):
        self.start()
        self.approve()
        self.plan.write_text("Changed scope", encoding="utf-8")
        self.assertFalse(d.guard(self.root, "sample")["execution_ready"])

    def test_graph_or_method_change_invalidates_approval(self):
        self.start()
        self.approve()
        self.record["tasks"][0]["checks"][0]["method"] = "other method"
        self.save()
        self.assertFalse(d.guard(self.root, "sample")["execution_ready"])

    def test_progress_and_usage_updates_do_not_invalidate_approval(self):
        self.start()
        self.approve()
        self.record["tasks"][0].update({"state": "REPAIRING", "repairs": 1, "used_minutes": 5})
        self.save()
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])

    def test_unapproved_task_cannot_execute(self):
        self.start()
        second = copy.deepcopy(self.record["tasks"][0])
        second.update({"id": "T02", "checks": [self.check_def("C3")]})
        self.record["tasks"].append(second)
        self.approve(["T01"])
        self.assertEqual(d.guard(self.root, "sample")["next_tasks"], ["T01"])
        self.record["tasks"][1]["state"] = "RUNNING"
        self.save()
        self.assertIn("EXECUTION_GATE", self.codes(d.guard(self.root, "sample")))

    def test_authorized_done_task_can_deliver(self):
        self.complete()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertTrue(result["delivery_ready"])

    def test_unapproved_done_task_with_pass_evidence_cannot_deliver(self):
        self.start_two_tasks()
        self.approve(["T01"])
        self.finish_task("T01")
        self.finish_task("T02")
        self.accept()
        result = d.guard(self.root, "sample")
        self.assertEqual(result["check_results"], {"C1": "PASS", "C3": "PASS", "C2": "PASS"})
        self.assertIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertTrue(any(i["code"] == "DONE_AUTHORIZATION" and i["field"] == "T02"
                            for i in result["issues"]))
        self.assertFalse(result["record_valid"])
        self.assertFalse(result["delivery_ready"])

    def test_unapproved_pending_task_is_not_an_unauthorized_done(self):
        self.start_two_tasks()
        self.approve(["T01"])
        self.finish_task("T01")
        self.accept()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertNotIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertFalse(result["delivery_ready"])

    def test_done_from_retained_batch_survives_current_batch_change(self):
        self.complete_two_batches()
        before = self.record_path.read_bytes()
        result = d.guard(self.root, "sample")
        self.assertEqual(self.record["approval"]["tasks"], ["T02"])
        self.assertEqual(self.record["approval_history"][0]["tasks"], ["T01"])
        self.assertTrue(result["record_valid"])
        self.assertTrue(result["delivery_ready"])
        for key, value in result["baseline"].items():
            self.assertEqual(self.record["approval_history"][0][key], value)
        self.assertEqual(self.record_path.read_bytes(), before)

    def test_missing_history_is_not_inferred_from_done_or_pass(self):
        self.complete_two_batches()
        del self.record["approval_history"]
        self.save()
        before = self.record_path.read_bytes()
        result = d.guard(self.root, "sample")
        self.assertIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertFalse(result["delivery_ready"])
        self.assertEqual(self.record_path.read_bytes(), before)

    def test_retained_approval_does_not_authorize_new_activity(self):
        self.complete_two_batches()
        self.record["tasks"][0]["state"] = "RUNNING"
        self.save()
        result = d.guard(self.root, "sample")
        self.assertIn("EXECUTION_GATE", self.codes(result))
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["delivery_ready"])

    def test_old_done_approval_cannot_cross_plan_or_graph_changes(self):
        self.complete_two_batches()
        original = copy.deepcopy(self.record)
        plan_bytes = self.plan.read_bytes()
        for change in ("plan", "graph"):
            with self.subTest(change=change):
                self.record = copy.deepcopy(original)
                self.plan.write_bytes(plan_bytes)
                if change == "plan":
                    self.plan.write_text("Revised design requiring approval", encoding="utf-8")
                else:
                    self.record["tasks"][0]["title"] = "Revised task definition"
                self.approve(["T02"])
                self.evidence("C1")
                self.evidence("C3")
                self.evidence("C2")
                result = d.guard(self.root, "sample")
                self.assertEqual(result["check_results"], {"C1": "PASS", "C3": "PASS", "C2": "PASS"})
                self.assertTrue(any(i["code"] == "DONE_AUTHORIZATION" and i["field"] == "T01"
                                    for i in result["issues"]))
                self.assertFalse(result["delivery_ready"])

    def test_incomplete_or_out_of_scope_approval_history_is_rejected(self):
        self.complete_two_batches()
        original = copy.deepcopy(self.record)
        changes = [
            {"decision": "REJECTED"}, {"reviewer": ""}, {"at": ""}, {"source": " "},
            {"plan_sha256": "invalid"}, {"tasks": ["missing"]}, {"paths": ["tests"]},
            {"paths": ["../outside"]}, {"operations": []},
            {"limits": {"max_repairs": None, "max_minutes": None}},
            {"limits": {"max_repairs": True, "max_minutes": 60}},
        ]
        for changeset in changes:
            with self.subTest(changeset=changeset):
                self.record = copy.deepcopy(original)
                self.record["approval_history"][0].update(changeset)
                self.save()
                result = d.guard(self.root, "sample")
                self.assertIn("APPROVAL_HISTORY", self.codes(result))
                self.assertFalse(result["delivery_ready"])

    def test_approval_history_requires_full_snapshots(self):
        self.complete_two_batches()
        for history in ({}, [None], ["T01 was DONE"], [{"tasks": ["T01"], "source": "Inferred from PASS"}]):
            with self.subTest(history=history):
                self.record["approval_history"] = history
                self.save()
                result = d.guard(self.root, "sample")
                self.assertIn("APPROVAL_HISTORY", self.codes(result))
                self.assertFalse(result["delivery_ready"])

    def test_retained_approval_does_not_hide_excess_repairs(self):
        self.complete_two_batches()
        self.record["tasks"][0]["repairs"] = 4
        self.save()
        result = d.guard(self.root, "sample")
        self.assertIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertFalse(result["delivery_ready"])

    def test_approval_history_does_not_replace_current_approval(self):
        self.complete_two_batches()
        self.record["approval_history"].append(copy.deepcopy(self.record["approval"]))
        self.record["approval"]["decision"] = "PENDING"
        self.save()
        result = d.guard(self.root, "sample")
        self.assertNotIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertFalse(result["delivery_ready"])

    def test_scope_boundary_cannot_be_escaped(self):
        self.start()
        self.approve()
        self.record["approval"]["paths"] = ["tests"]
        self.save()
        self.assertIn("APPROVAL_SCOPE", self.codes(d.guard(self.root, "sample")))

    def test_cycle_and_missing_dependency_are_rejected(self):
        self.start()
        self.record["tasks"][0]["depends_on"] = ["T01"]
        self.save()
        self.assertIn("CYCLE", self.codes(d.guard(self.root, "sample")))
        self.record["tasks"][0]["depends_on"] = ["missing"]
        self.save()
        self.assertIn("DEPENDENCY", self.codes(d.guard(self.root, "sample")))

    def test_done_cannot_be_claimed_without_current_evidence(self):
        self.start()
        self.approve()
        self.record["tasks"][0]["state"] = "DONE"
        self.save()
        self.assertIn("FALSE_DONE", self.codes(d.guard(self.root, "sample")))

    def test_source_or_report_changes_invalidate_pass(self):
        self.complete()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        result = d.guard(self.root, "sample")
        self.assertFalse(result["delivery_ready"])
        self.assertEqual(result["check_results"]["C1"], "NOT_VERIFIED")
        self.assertIn("FALSE_DONE", self.codes(result))

    def test_modified_raw_report_cannot_remain_pass(self):
        self.complete()
        (self.root / "report-C2.txt").write_text("Changed report", encoding="utf-8")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])

    def test_unauthorized_verification_method_is_rejected(self):
        self.complete()
        self.record["evidence"][0]["method"] = "mock instead of required live check"
        self.save()
        self.assertIn("METHOD_CHANGED", self.codes(d.guard(self.root, "sample")))

    def test_task_completion_is_distinct_from_overall_acceptance(self):
        self.start()
        self.approve()
        self.evidence("C1")
        self.record["tasks"][0]["state"] = "DONE"
        self.save()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertFalse(result["delivery_ready"])

    def test_unknown_conditional_applicability_prevents_completion(self):
        self.complete()
        self.record["tasks"][0]["checks"].append({**self.check_def("C3"),
            "kind": "CONDITIONAL", "trigger": "UNKNOWN"})
        self.approve()
        self.assertIn("FALSE_DONE", self.codes(d.guard(self.root, "sample")))

    def test_nontriggered_conditional_needs_reason(self):
        self.start()
        self.record["tasks"][0]["checks"].append({**self.check_def("C3"),
            "kind": "CONDITIONAL", "trigger": "NOT_TRIGGERED"})
        self.save()
        self.assertIn("TRIGGER", self.codes(d.guard(self.root, "sample")))

    def test_later_live_followup_does_not_block_current_delivery(self):
        self.complete()
        self.record["followups"] = [{"id": "F01", "goal": "Hosted integration",
            "method": "Hosted smoke test", "reason": "Outside this approved local scope",
            "resume": "Provide staging account and run the documented smoke test",
            "required_for_scope": False, "status": "NOT_VERIFIED"}]
        self.approve()
        self.evidence("C1")
        self.evidence("C2")
        result = d.guard(self.root, "sample")
        self.assertTrue(result["delivery_ready"])
        self.assertEqual(result["followups_pending"], ["F01"])

    def test_required_check_cannot_be_hidden_in_followups(self):
        self.start()
        self.record["followups"] = [{"required_for_scope": True}]
        self.save()
        self.assertIn("FOLLOWUP", self.codes(d.guard(self.root, "sample")))

    def test_null_limits_never_mean_unlimited_execution(self):
        self.start()
        self.approve()
        self.record["approval"]["limits"] = {"max_repairs": None, "max_minutes": None}
        self.save()
        self.assertFalse(d.guard(self.root, "sample")["execution_ready"])

    def test_last_permitted_repair_can_be_verified_but_excess_is_rejected(self):
        self.start()
        self.approve()
        self.record["tasks"][0].update({"state": "VERIFYING", "repairs": 3})
        self.save()
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])
        self.record["tasks"][0]["repairs"] = 4
        self.save()
        self.assertIn("LIMIT_EXCEEDED", self.codes(d.guard(self.root, "sample")))

    def test_recorded_time_limit_stops_execution(self):
        self.start()
        self.approve()
        self.record["tasks"][0]["used_minutes"] = 60
        self.save()
        self.assertFalse(d.guard(self.root, "sample")["execution_ready"])

    def test_knowledge_draft_can_be_handed_off_without_live_environment(self):
        self.complete()
        self.record["handoff"]["knowledge"] = {"status": "DRAFT_READY", "refs": ["README.md"]}
        self.save()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_missing_handoff_documents_prevent_completion(self):
        self.complete()
        self.record["handoff"]["docs"] = []
        self.save()
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])

    def test_malformed_cli_input_returns_json_and_nonzero_exit(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "guard", "--project", str(self.root),
            "--id", "../bad"], capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "ERROR")

    def test_reverify_preserves_old_evidence_without_stale_waiting(self):
        self.complete()
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        self.evidence("C1")
        self.evidence("C2")
        result = d.guard(self.root, "sample")
        self.assertTrue(result["delivery_ready"])
        self.assertFalse(any("missing or changed" in x for x in result["waiting"]))
        self.assertEqual(len(self.record["evidence"]), 4)

    def test_evidence_from_previous_approved_plan_is_history_only(self):
        self.complete()
        self.plan.write_text("Revised approved requirement", encoding="utf-8")
        self.approve()
        self.record["tasks"][0]["state"] = "VERIFYING"
        self.save()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertEqual(result["check_results"], {})
        self.assertFalse(result["delivery_ready"])
        self.evidence("C1")
        self.evidence("C2")
        self.record["tasks"][0]["state"] = "DONE"
        self.save()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_executed_evidence_without_baseline_is_rejected(self):
        self.complete()
        del self.record["evidence"][0]["baseline"]
        self.save()
        self.assertIn("EVIDENCE_BASELINE", self.codes(d.guard(self.root, "sample")))

    def test_blocked_task_requires_actionable_resume_notes(self):
        self.start()
        self.record["tasks"][0]["state"] = "BLOCKED"
        self.record["handoff"]["resume"] = ""
        self.save()
        self.assertIn("RESUME", self.codes(d.guard(self.root, "sample")))

    def test_empty_acceptance_cannot_authorize_implementation(self):
        self.start()
        self.record["tasks"][0]["checks"] = []
        self.approve()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertFalse(result["execution_ready"])

    def test_latest_failed_retest_overrides_an_earlier_pass(self):
        self.complete()
        self.evidence("C1", "FAIL")
        result = d.guard(self.root, "sample")
        self.assertEqual(result["check_results"]["C1"], "FAIL")
        self.assertFalse(result["delivery_ready"])


if __name__ == "__main__":
    unittest.main()
