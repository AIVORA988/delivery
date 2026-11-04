"""Observable installer and acceptance invariants; no network or application services."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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
        # A parent directory may itself be a repository on a developer's machine.
        discovery = mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root.parent)})
        discovery.start()
        self.addCleanup(discovery.stop)
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
        self.record["handoff"].update({"artifacts": ["src.py"], "docs": ["README.md"],
            "knowledge": {"status": "NO_INCREMENT", "reason": "Sample README already sufficient"}})
        self.receive()

    def receive(self):
        self.record["overall"].update({"accepted_by": "Fixture receiver",
            "accepted_at": "2026-10-22T10:10:00+08:00", "source": "Fixture acceptance"})
        self.save()
        self.record["overall"]["accepted_sha256"] = d.guard(self.root, "sample")["acceptance_sha256"]
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

    def git(self, *args):
        if not shutil.which("git"):
            self.skipTest("Git is unavailable")
        return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false",
            "-c", "user.name=Test fixture", "-c", "user.email=fixture@example.invalid",
            "-c", f"core.hooksPath={self.temp.name}/no-hooks", "-C", self.temp.name, *args],
            capture_output=True, check=True).stdout

    def start_git(self, commit=True):
        if not (self.root / ".git").exists():
            self.git("init", "--quiet")
            self.git("add", "src.py", "README.md")
            if commit:
                self.git("commit", "--quiet", "-m", "Fixture baseline")
        self.start()
        self.record["tasks"][0]["paths"] += ["README.md", "report-C1.txt", "report-C2.txt"]
        self.approve()
        self.record["approval"]["paths"] = ["."]
        self.save()

    def test_git_scope_rejects_outside_changes_and_final_receipt(self):
        self.start_git()
        self.finish_task("T01")
        self.accept()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        other = self.root / "outside.txt"
        other.write_text("Unapproved new file", encoding="utf-8")
        for staged in (False, True):
            with self.subTest(staged=staged):
                if staged:
                    self.git("add", "outside.txt")
                result = d.guard(self.root, "sample")
                self.assertEqual(result["change_scope"]["outside"], ["outside.txt"])
                self.assertIn("CHANGE_SCOPE", self.codes(result))
                self.assertFalse(result["delivery_ready"])
                self.assertIsNone(result["acceptance_sha256"])

    def test_git_scope_checks_deletion_rename_and_committed_changes(self):
        other = self.root / "outside.txt"
        other.write_text("Original", encoding="utf-8")
        self.start_git()
        # outside.txt was already present at the start; unchanged content is ignored.
        self.assertEqual(d.guard(self.root, "sample")["change_scope"]["changed"], [])
        self.git("add", "outside.txt")
        self.git("commit", "--quiet", "-m", "Stage preexisting fixture")
        self.assertEqual(d.guard(self.root, "sample")["change_scope"]["outside"], ["outside.txt"])
        other.rename(self.root / "renamed.txt")
        result = d.guard(self.root, "sample")
        self.assertEqual(result["change_scope"]["outside"], ["outside.txt", "renamed.txt"])
        (self.root / "renamed.txt").unlink()
        self.assertEqual(d.guard(self.root, "sample")["change_scope"]["outside"], ["outside.txt"])

    def test_git_scope_keeps_original_dirty_files_and_detects_later_edits(self):
        self.git("init", "--quiet")
        self.git("add", "src.py", "README.md")
        self.git("commit", "--quiet", "-m", "Fixture baseline")
        (self.root / "README.md").write_text("Already edited", encoding="utf-8")
        self.git("add", "README.md")
        (self.root / "preexisting.txt").write_text("Already present", encoding="utf-8")
        self.start_git()
        self.record["tasks"][0]["paths"] = ["src.py"]
        self.approve()
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])
        for ref in ("README.md", "preexisting.txt"):
            with self.subTest(path=ref):
                (self.root / ref).write_text("Later edit", encoding="utf-8")
                self.assertIn(ref, d.guard(self.root, "sample")["change_scope"]["outside"])

    def test_git_scope_detects_staged_change_even_when_worktree_is_restored(self):
        self.start_git()
        original = (self.root / "README.md").read_bytes()
        self.record["tasks"][0]["paths"] = ["src.py"]
        self.approve()
        (self.root / "README.md").write_text("Staged change", encoding="utf-8")
        self.git("add", "README.md")
        (self.root / "README.md").write_bytes(original)
        self.assertEqual(d.guard(self.root, "sample")["change_scope"]["outside"], ["README.md"])

    def test_git_scope_accepts_authorized_changes_without_mutating_index(self):
        self.start_git()
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        self.git("add", "src.py")
        self.git("commit", "--quiet", "-m", "Authorized fixture change")
        self.finish_task("T01")
        self.accept()
        before = (self.root / ".git/index").read_bytes()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["delivery_ready"], result["issues"])
        self.assertEqual(result["change_scope"]["status"], "PASS")
        self.assertIn("src.py", result["change_scope"]["changed"])
        self.assertEqual(before, (self.root / ".git/index").read_bytes())

    def test_git_scope_supports_unborn_head_and_project_subdirectories(self):
        self.start_git(commit=False)
        self.assertIsNone(self.record["workspace"]["head"])
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])
        # Committing unchanged, already staged input does not manufacture a change.
        self.git("commit", "--quiet", "-m", "First fixture commit")
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])
        project = self.root / "nested"
        project.mkdir()
        (project / "中文.txt").write_text("Nested original", encoding="utf-8")
        self.git("add", "nested")
        self.git("commit", "--quiet", "-m", "Nested fixture")
        baseline = d.git_snapshot(project, "nested")
        self.assertEqual(baseline["dirty"], {})
        (project / "中文.txt").write_text("Nested edit", encoding="utf-8")
        (self.root / "sibling.txt").write_text("Sibling", encoding="utf-8")
        current = d.git_snapshot(project, "nested", baseline["head"])
        self.assertEqual(set(current["dirty"]), {"中文.txt"})

    def test_git_scope_preserves_completed_batch_authorization(self):
        self.start_git()
        second = copy.deepcopy(self.record["tasks"][0])
        second.update({"id": "T02", "title": "Next task", "paths": ["next.py"],
            "state": "PENDING", "depends_on": ["T01"], "checks": [self.check_def("C3")]})
        self.record["tasks"].append(second)
        self.approve(["T01"])
        self.record["approval"]["paths"] = ["."]
        self.save()
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        (self.root / "next.py").write_text("Unauthorized pending task", encoding="utf-8")
        self.assertEqual(d.guard(self.root, "sample")["change_scope"]["outside"], ["next.py"])
        (self.root / "next.py").unlink()
        self.finish_task("T01")
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.approve(["T02"])
        self.record["approval"]["paths"] = ["next.py"]
        self.record["tasks"][1]["state"] = "READY"
        self.save()
        result = d.guard(self.root, "sample", "T02")
        self.assertTrue(result["execution_ready"], result["issues"])
        self.assertEqual(result["change_scope"]["outside"], [])

    def test_git_scope_baseline_is_approval_bound_and_unavailable_git_blocks(self):
        self.start_git()
        original = copy.deepcopy(self.record["workspace"])
        self.record["workspace"]["head"] = None
        self.save()
        self.assertFalse(d.guard(self.root, "sample")["execution_ready"])
        self.record["workspace"] = original
        self.save()
        (self.root / ".git").rename(self.root / "git-hidden")
        result = d.guard(self.root, "sample")
        self.assertEqual(result["change_scope"]["status"], "NOT_VERIFIED")
        self.assertFalse(result["execution_ready"])

    def test_legacy_record_does_not_invent_a_git_baseline(self):
        self.start_git()
        self.record.pop("workspace")
        self.approve()
        self.record["approval"]["paths"] = ["."]
        self.save()
        self.finish_task("T01")
        self.accept()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["delivery_ready"], result["issues"])
        self.assertEqual(result["change_scope"]["status"], "NOT_CONFIGURED")
        self.assertNotIn("workspace", d.read_json(self.record_path))

    def test_git_scope_rejects_malformed_original_snapshots(self):
        self.start_git()
        for value in ({}, {"head": 1, "dirty": {}}, {"head": None, "dirty": []},
                      {"head": None, "dirty": {"../outside": {"worktree": None, "index": None}}},
                      {"head": None, "dirty": {"file": {"worktree": "PASS", "index": None}}}):
            with self.subTest(value=value):
                self.record["workspace"] = value
                self.save()
                result = d.guard(self.root, "sample")
                self.assertIn("WORKSPACE", self.codes(result))
                self.assertFalse(result["delivery_ready"])

    def test_non_git_project_reports_manual_change_scope_review(self):
        self.complete()
        self.assertIsNone(self.record["workspace"])
        result = d.guard(self.root, "sample")
        self.assertEqual(result["change_scope"]["status"], "NOT_CONFIGURED")
        self.assertTrue(result["delivery_ready"])

    def test_git_scope_allows_bound_planning_inputs_and_only_current_run_records(self):
        self.start_git()
        design = self.root / "docs/api.md"
        design.write_text("Approved stable API contract", encoding="utf-8")
        self.record["contracts"] = ["docs/api.md"]
        self.approve()
        self.record["approval"]["paths"] = ["."]
        self.save()
        (self.record_path.parent / "report.txt").write_text("Run-local report", encoding="utf-8")
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])
        (self.root / ".delivery/unapproved.txt").write_text("Other file", encoding="utf-8")
        result = d.guard(self.root, "sample")
        self.assertEqual(result["change_scope"]["outside"], [".delivery/unapproved.txt"])

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

    def test_init_installs_five_skills_and_only_the_knowledge_entry(self):
        before = (self.root / "src.py").read_bytes()
        result = d.initialize(self.root)
        installed = self.root / ".agents/skills"
        expected = {"delivery", "delivery-run", "delivery-feature", "delivery-feature-run", "delivery-bootstrap"}
        self.assertEqual({p.name for p in installed.iterdir()}, expected)
        self.assertEqual(set(result["skills"]), expected)
        self.assertTrue((installed / "delivery-bootstrap/SKILL.md").is_file())
        self.assertTrue((installed / "delivery/references/knowledge.md").is_file())
        metadata = (installed / "delivery/agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('  display_name: "delivery"\n', metadata)
        knowledge = self.root / "docs/knowledge"
        self.assertEqual([p.name for p in knowledge.iterdir()], ["README.md"])
        checked = d.check(self.root)
        self.assertEqual(checked["status"], "CONFIGURED")
        self.assertIs(checked["knowledge"]["empty"], True)
        self.assertEqual(checked["knowledge"]["candidates"], [])
        self.assertEqual((self.root / "src.py").read_bytes(), before)

    def test_existing_knowledge_and_custom_config_survive_init(self):
        d.initialize(self.root)
        entry = self.root / "docs/knowledge/README.md"
        entry.write_bytes(b"# Existing navigation\r\nKeep human annotations.\r\n")
        existing = self.root / "docs/api.md"
        existing.write_bytes(b"# Existing API\nSource: src.py\n")
        path = self.root / ".delivery/project.json"
        config = d.read_json(path)
        config.update({"knowledge_paths": ["docs/api.md", "docs/api.md"], "team_setting": {"keep": True}})
        path.write_bytes(d.packed(config))
        snapshot = (entry.read_bytes(), existing.read_bytes())
        d.initialize(self.root)
        self.assertEqual((entry.read_bytes(), existing.read_bytes()), snapshot)
        config = d.read_json(path)
        self.assertEqual(config["knowledge_paths"], ["docs/api.md", "docs/knowledge"])
        self.assertEqual(config["team_setting"], {"keep": True})
        self.assertEqual(d.initialize(self.root)["written"], 0)
        checked = d.check(self.root)
        self.assertIs(checked["knowledge"]["empty"], False)
        self.assertIn("docs/api.md", checked["knowledge"]["candidates"])

    def test_knowledge_conflict_aborts_before_installing_either_skill(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/knowledge").write_text("Do not replace this file", encoding="utf-8")
        with self.assertRaises(ValueError):
            d.initialize(self.root)
        self.assertFalse((self.root / ".agents").exists())
        self.assertFalse((self.root / ".delivery").exists())

    def test_companion_conflict_aborts_before_creating_missing_knowledge(self):
        d.initialize(self.root)
        entry = self.root / "docs/knowledge/README.md"
        entry.unlink()
        companion = self.root / ".agents/skills/delivery-bootstrap/SKILL.md"
        companion.write_text("Human edit", encoding="utf-8")
        before = (self.root / ".delivery/install.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "Local edit/conflict"):
            d.initialize(self.root)
        self.assertFalse(entry.exists())
        self.assertEqual((self.root / ".delivery/install.json").read_bytes(), before)

    def test_legacy_install_upgrades_without_changing_approved_run(self):
        self.complete()
        run_before = (self.plan.read_bytes(), self.record_path.read_bytes())
        receipt_path = self.root / ".delivery/install.json"
        receipt = d.read_json(receipt_path)
        del receipt["companions"]
        old_skill = self.root / ".agents/skills/delivery/SKILL.md"
        old_skill.write_text("Previous managed Skill\n", encoding="utf-8")
        receipt["files"]["SKILL.md"] = d.digest(old_skill.read_bytes())
        receipt_path.write_bytes(d.packed(receipt))
        shutil.rmtree(self.root / ".agents/skills/delivery-bootstrap")
        config_path = self.root / ".delivery/project.json"
        config = d.read_json(config_path)
        config.pop("knowledge_paths")
        config_path.write_bytes(d.packed(config))
        d.initialize(self.root)
        self.assertEqual(d.check(self.root)["status"], "CONFIGURED")
        self.assertEqual((self.plan.read_bytes(), self.record_path.read_bytes()), run_before)
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_installed_package_can_initialize_another_project(self):
        d.initialize(self.root)
        target = self.root / "another-project"
        target.mkdir()
        script = self.root / ".agents/skills/delivery/scripts/delivery.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(script), "init", "--project", str(target)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(d.check(target)["status"], "CONFIGURED")

    def test_missing_companion_source_aborts_without_partial_install(self):
        d.initialize(self.root)
        shutil.rmtree(self.root / ".agents/skills/delivery-bootstrap")
        target = self.root / "unconfigured-project"
        target.mkdir()
        script = self.root / ".agents/skills/delivery/scripts/delivery.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(script), "init", "--project", str(target)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Incomplete distribution", result.stdout)
        self.assertEqual(list(target.iterdir()), [])

    def test_empty_index_does_not_hide_existing_body_or_readme_content(self):
        d.initialize(self.root)
        body = self.root / "docs/knowledge/modules/orders.md"
        body.parent.mkdir()
        body.write_text("# Orders\nCurrent static rule; source: src.py\n", encoding="utf-8")
        result = d.check(self.root)["knowledge"]
        self.assertIs(result["empty"], False)
        self.assertIn("docs/knowledge/modules/orders.md", result["candidates"])
        body.unlink()
        entry = self.root / "docs/knowledge/README.md"
        entry.write_text("# Existing knowledge in the entry itself\n", encoding="utf-8")
        self.assertIs(d.check(self.root)["knowledge"]["empty"], False)

    def test_truncated_or_unavailable_knowledge_is_not_reported_empty(self):
        d.initialize(self.root)
        deep = self.root / "docs/knowledge/a/b/c/d/e/f/g"
        deep.mkdir(parents=True)
        context = d.check(self.root)["knowledge"]
        self.assertTrue(context["truncated"])
        self.assertIsNone(context["empty"])

        context = d.knowledge_context(self.root, ["missing-documents"])
        self.assertIsNone(context["empty"])
        self.assertEqual(context["unavailable"], ["missing-documents"])

    def test_invalid_knowledge_paths_do_not_reset_config_or_install(self):
        for paths in (None, "docs", ["../outside"], ["C:/outside"], [""]):
            with self.subTest(paths=paths):
                config = self.root / ".delivery/project.json"
                config.parent.mkdir(exist_ok=True)
                raw = d.packed({"schema_version": 1, "workflow": "V1.0", "knowledge_paths": paths})
                config.write_bytes(raw)
                with self.assertRaises(ValueError):
                    d.initialize(self.root)
                self.assertEqual(config.read_bytes(), raw)
                self.assertFalse((self.root / ".agents").exists())

    def test_knowledge_scan_budget_includes_ignored_entries(self):
        d.initialize(self.root)
        folder = self.root / "docs/knowledge"
        for number in range(1001):
            (folder / f".ignored-{number}").touch()
        context = d.check(self.root)["knowledge"]
        self.assertTrue(context["truncated"])
        self.assertIsNone(context["empty"])
        config_path = self.root / ".delivery/project.json"
        config = d.read_json(config_path)
        config["knowledge_paths"].append("../outside")
        config_path.write_bytes(d.packed(config))
        with self.assertRaisesRegex(ValueError, "Unsafe project-relative"):
            d.check(self.root)

    def test_knowledge_updates_preserve_baseline_but_changed_evidence_still_expires(self):
        self.complete()
        baseline = d.guard(self.root, "sample")["baseline"]
        entry = self.root / "docs/knowledge/README.md"
        entry.write_text("# A genuine documentation update\nSource: src.py\n", encoding="utf-8")
        self.record["handoff"]["knowledge"] = {"status": "UPDATED", "refs": ["docs/knowledge/README.md"]}
        self.save()
        result = d.guard(self.root, "sample")
        self.assertEqual(result["baseline"], baseline)
        self.assertTrue(result["delivery_ready"])
        self.assertEqual(d.check(self.root)["status"], "CONFIGURED")
        self.record["evidence"][0]["subjects"].append(
            {"path": "docs/knowledge/README.md", "sha256": d.digest(entry.read_bytes())})
        self.receive()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        entry.write_text("# Checked documentation changed again\n", encoding="utf-8")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])

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

    def test_final_receipt_digest_is_unavailable_until_tasks_are_done(self):
        self.start()
        self.approve()
        self.evidence("C1")
        self.record["tasks"][0]["state"] = "VERIFYING"
        self.accept()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertIsNone(result["acceptance_sha256"])
        self.record["tasks"][0]["state"] = "DONE"
        self.save()
        result = d.guard(self.root, "sample")
        self.assertIsNotNone(result["acceptance_sha256"])
        self.assertFalse(result["delivery_ready"])
        self.receive()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_final_receipt_digest_requires_all_delivery_prerequisites(self):
        self.complete()
        original = copy.deepcopy(self.record)
        for kind in ("task_check", "authorization", "usage", "knowledge", "overall", "files"):
            with self.subTest(kind=kind):
                self.record = copy.deepcopy(original)
                if kind == "task_check":
                    self.record["evidence"][0]["result"] = "NOT_RUN"
                elif kind == "authorization":
                    self.record["approval"]["decision"] = "PENDING"
                elif kind == "usage":
                    self.record["tasks"][0]["used_minutes"] = 61
                elif kind == "knowledge":
                    self.record["handoff"]["knowledge"] = {"status": "PENDING"}
                elif kind == "overall":
                    self.record["evidence"][-1]["result"] = "NOT_RUN"
                else:
                    self.record["handoff"]["docs"] = []
                self.save()
                result = d.guard(self.root, "sample")
                self.assertIsNone(result["acceptance_sha256"])
                self.assertFalse(result["delivery_ready"])

    def test_reverification_cannot_reuse_receipt_for_previous_artifact_version(self):
        self.complete()
        receipt = copy.deepcopy(self.record["overall"])
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        self.evidence("C1")
        self.evidence("C2")
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertTrue(result["batch_complete"])
        self.assertEqual(set(result["check_results"].values()), {"PASS"})
        self.assertEqual(self.record["overall"], receipt)
        self.assertFalse(result["delivery_ready"])

    def test_changed_handoff_file_cannot_reuse_receipt(self):
        self.complete()
        for field in ("artifacts", "docs"):
            with self.subTest(field=field):
                added = self.root / f"additional-{field}.txt"
                added.write_text("Original delivered content\n", encoding="utf-8")
                self.record["handoff"][field].append(added.name)
                self.save()
                self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
                self.receive()
                self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
                added.write_text("Changed delivered content\n", encoding="utf-8")
                result = d.guard(self.root, "sample")
                self.assertEqual(set(result["check_results"].values()), {"PASS"})
                self.assertFalse(result["delivery_ready"])
                self.record["handoff"][field].remove(added.name)

    def test_new_baseline_and_fresh_checks_do_not_reconfirm_receipt(self):
        self.complete()
        self.plan.write_text("Revised approved design\n", encoding="utf-8")
        self.approve()
        self.evidence("C1")
        self.evidence("C2")
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertTrue(result["batch_complete"])
        self.assertFalse(result["delivery_ready"])
        self.receive()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_receipt_binds_all_required_evidence_and_in_place_report_changes(self):
        self.complete()
        for cid in ("C1", "C2"):
            with self.subTest(check=cid):
                self.evidence(cid)
                self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
                self.receive()
                self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        report = self.root / "report-C2.txt"
        report.write_text("New actual results for the same check\n", encoding="utf-8")
        self.record["evidence"][-1]["report"]["sha256"] = d.digest(report.read_bytes())
        self.save()
        result = d.guard(self.root, "sample")
        self.assertEqual(result["check_results"]["C2"], "PASS")
        self.assertFalse(result["delivery_ready"])

    def test_missing_legacy_receipt_binding_preserves_approval_and_task_progress(self):
        self.complete_two_batches()
        del self.record["overall"]["accepted_sha256"]
        self.save()
        before = self.record_path.read_bytes()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"])
        self.assertTrue(result["batch_complete"])
        self.assertFalse(result["delivery_ready"])
        self.assertEqual(self.record_path.read_bytes(), before)
        self.receive()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_receipt_hash_alone_cannot_replace_actual_receipt_metadata(self):
        self.complete()
        for key in ("accepted_by", "accepted_at", "source", "accepted_sha256"):
            with self.subTest(key=key):
                original = self.record["overall"][key]
                self.record["overall"][key] = ""
                self.save()
                self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
                self.record["overall"][key] = original

    def test_receipt_ignores_batch_progress_and_optional_knowledge_updates(self):
        self.complete_two_batches()
        baseline = d.guard(self.root, "sample")["baseline"]
        receipt = self.record["overall"]["accepted_sha256"]
        self.record["tasks"][1]["used_minutes"] = 5
        self.record["approval_history"].append(copy.deepcopy(self.record["approval"]))
        self.approve(["T01"])
        entry = self.root / "docs/knowledge/README.md"
        entry.write_text("# Reusable finding\nSource: src.py\n", encoding="utf-8")
        self.record["handoff"]["knowledge"] = {"status": "UPDATED", "refs": ["docs/knowledge/README.md"]}
        self.record["handoff"]["resume"] = "No pending task; retain existing history"
        self.save()
        result = d.guard(self.root, "sample")
        self.assertEqual(result["baseline"], baseline)
        self.assertEqual(result["acceptance_sha256"], receipt)
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
        self.receive()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["delivery_ready"])
        self.assertEqual(result["followups_pending"], ["F01"])
        receipt = result["acceptance_sha256"]
        self.record["followups"][0]["status"] = "FAIL"
        self.save()
        result = d.guard(self.root, "sample")
        self.assertEqual(result["acceptance_sha256"], receipt)
        self.assertTrue(result["delivery_ready"])

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

    def test_done_time_limit_accepts_exact_completion_but_rejects_overrun(self):
        self.complete()
        for used, allowed in ((59, True), (60, True), (61, False)):
            with self.subTest(used=used):
                self.record["tasks"][0]["used_minutes"] = used
                self.save()
                result = d.guard(self.root, "sample")
                self.assertEqual(result["delivery_ready"], allowed)
                self.assertEqual(result["batch_complete"], allowed)
                if not allowed:
                    self.assertIn("DONE_AUTHORIZATION", self.codes(result))

    def test_historical_done_must_fit_its_original_time_limit(self):
        self.complete_two_batches()
        self.record["tasks"][0]["used_minutes"] = 61
        self.save()
        result = d.guard(self.root, "sample")
        self.assertIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertFalse(result["delivery_ready"])
        self.record["tasks"][0]["used_minutes"] = 60
        self.save()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_current_limits_do_not_retroactively_reject_valid_historical_done(self):
        self.start_two_tasks()
        self.approve(["T01"])
        self.record["tasks"][0].update({"repairs": 2, "used_minutes": 40})
        self.finish_task("T01")
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.approve(["T01", "T02"])
        self.record["approval"]["limits"] = {"max_repairs": 0, "max_minutes": 10}
        self.record["tasks"][1]["state"] = "READY"
        self.save()
        result = d.guard(self.root, "sample", "T02")
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["execution_ready"])
        self.finish_task("T02")
        self.accept()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        self.record["tasks"][0]["state"] = "VERIFYING"
        self.save()
        self.assertFalse(d.guard(self.root, "sample", "T01")["execution_ready"])

    def test_repairing_requires_a_registered_attempt_and_preserves_last_reverify(self):
        self.start()
        self.approve()
        self.record["tasks"][0]["state"] = "REPAIRING"
        for maximum in (3, 0):
            with self.subTest(maximum=maximum):
                self.record["approval"]["limits"]["max_repairs"] = maximum
                self.save()
                result = d.guard(self.root, "sample", "T01")
                self.assertIn("REPAIR_STATE", self.codes(result))
                self.assertFalse(result["execution_ready"])
        self.record["approval"]["limits"]["max_repairs"] = 3
        for state, repairs, allowed in (("REPAIRING", 1, True), ("REPAIRING", 3, True),
                                        ("VERIFYING", 3, True), ("REPAIRING", 4, False)):
            with self.subTest(state=state, repairs=repairs):
                self.record["tasks"][0].update({"state": state, "repairs": repairs})
                self.save()
                self.assertEqual(d.guard(self.root, "sample", "T01")["execution_ready"], allowed)

    def test_only_nontriggered_checks_cannot_authorize_unfinishable_work(self):
        self.start()
        self.record["tasks"][0]["checks"][0].update({"kind": "CONDITIONAL",
            "trigger": "NOT_TRIGGERED", "reason": "No applicable path in this scope"})
        self.approve()
        self.assertFalse(d.guard(self.root, "sample", "T01")["execution_ready"])
        self.record["tasks"][0]["checks"].append(self.check_def("C3"))
        self.approve()
        self.assertTrue(d.guard(self.root, "sample", "T01")["execution_ready"])

    def test_blocking_optional_failure_needs_fresh_pass_not_stale_or_not_run(self):
        self.start()
        self.record["tasks"][0]["checks"].append({**self.check_def("O1"),
            "kind": "OPTIONAL", "failure_blocks": True})
        self.approve()
        self.finish_task("T01")
        self.accept()
        self.evidence("O1", "FAIL")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        self.evidence("C1")
        self.evidence("C2")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.evidence("O1", "NOT_RUN")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.evidence("O1")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.receive()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_nonblocking_optional_failure_preserves_optional_semantics(self):
        self.start()
        self.record["tasks"][0]["checks"].append({**self.check_def("O1"), "kind": "OPTIONAL"})
        self.approve()
        self.finish_task("T01")
        self.accept()
        self.evidence("O1", "FAIL")
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_unknown_condition_with_required_check_keeps_existing_execution_semantics(self):
        self.start()
        self.record["tasks"][0]["checks"].append({**self.check_def("C3"),
            "kind": "CONDITIONAL", "trigger": "UNKNOWN"})
        self.approve()
        self.assertTrue(d.guard(self.root, "sample", "T01")["execution_ready"])
        self.finish_task("T01")
        self.accept()
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])

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
        self.receive()
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
        self.receive()
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

    def test_legacy_graph_approval_digest_is_preserved(self):
        self.start()
        self.record.pop("scenario")
        self.record.pop("contracts", None)
        self.save()
        legacy = "6aeaf198e33754ff38ab6354b8a5284b15e399fdba22ab1712e4a99907f205af"
        self.assertEqual(d.guard(self.root, "sample")["baseline"]["graph_sha256"], legacy)
        self.record["contracts"] = []
        self.save()
        self.assertEqual(d.guard(self.root, "sample")["baseline"]["graph_sha256"], legacy)
        self.approve()
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])

    def test_bound_contract_change_invalidates_execution_and_historical_done(self):
        self.start_two_tasks()
        contract = self.root / "api.md"
        contract.write_text("GET /orders returns total in cents\n", encoding="utf-8")
        self.record["contracts"] = ["api.md"]
        self.approve(["T01"])
        self.finish_task("T01")
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.record["tasks"][1]["state"] = "READY"
        self.approve(["T02"])
        self.assertTrue(d.guard(self.root, "sample", "T02")["execution_ready"])
        baseline = d.guard(self.root, "sample")["baseline"]
        contract.write_text("GET /orders returns total in yuan\n", encoding="utf-8")
        stale = d.guard(self.root, "sample", "T02")
        self.assertNotEqual(stale["baseline"], baseline)
        self.assertFalse(stale["execution_ready"])
        self.assertFalse(stale["batch_complete"])
        self.assertFalse(stale["delivery_ready"])
        self.assertIn("DONE_AUTHORIZATION", self.codes(stale))
        self.assertIn("FALSE_DONE", self.codes(stale))
        self.assertEqual(stale["check_results"], {})
        self.approve(["T02"])
        self.assertFalse(d.guard(self.root, "sample", "T02")["execution_ready"])
        self.assertIn("DONE_AUTHORIZATION", self.codes(d.guard(self.root, "sample")))
        self.record["tasks"][0].update({"state": "VERIFYING", "repairs": 1, "used_minutes": 17})
        self.record["tasks"][1]["state"] = "PENDING"
        self.approve(["T01", "T02"])
        self.assertTrue(d.guard(self.root, "sample", "T01")["execution_ready"])
        self.finish_task("T01")
        self.record["tasks"][1]["state"] = "READY"
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T02")["execution_ready"])
        self.finish_task("T02")
        self.accept()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        retained = d.read_json(self.record_path)
        self.assertEqual((retained["tasks"][0]["repairs"], retained["tasks"][0]["used_minutes"]), (1, 17))
        self.assertEqual(len(retained["evidence"]), 4)

    def test_contract_change_invalidates_completed_delivery(self):
        self.start()
        contract = self.root / "api.md"
        contract.write_text("Stable API contract", encoding="utf-8")
        self.record["contracts"] = ["api.md"]
        self.approve()
        self.finish_task("T01")
        self.accept()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        contract.write_text("Changed API contract", encoding="utf-8")
        result = d.guard(self.root, "sample")
        self.assertFalse(result["delivery_ready"])
        self.assertFalse(result["batch_complete"])

    def test_contract_order_and_unrelated_docs_do_not_invalidate_approval(self):
        self.start()
        for name in ("api.md", "design.md"):
            (self.root / name).write_text(name, encoding="utf-8")
        self.record["contracts"] = ["api.md", "design.md"]
        self.approve()
        baseline = d.guard(self.root, "sample")["baseline"]
        self.record["contracts"].reverse()
        self.save()
        (self.root / "README.md").write_text("Unrelated usage clarification", encoding="utf-8")
        result = d.guard(self.root, "sample")
        self.assertEqual(result["baseline"], baseline)
        self.assertTrue(result["execution_ready"])
        self.record["contracts"] = ["api.md"]
        self.save()
        self.assertFalse(d.guard(self.root, "sample")["execution_ready"])

    def test_missing_malformed_and_self_referential_contracts_fail_closed(self):
        self.start()
        for refs in (None, "README.md", [1], ["missing.md"], ["README.md", "README.md"],
                     [".delivery/runs/sample/record.json"], ["docs"]):
            with self.subTest(refs=refs):
                self.record["contracts"] = refs
                self.save()
                before = self.record_path.read_bytes()
                result = d.guard(self.root, "sample")
                self.assertIn("CONTRACTS", self.codes(result))
                self.assertFalse(result["execution_ready"])
                self.assertFalse(result["delivery_ready"])
                self.assertEqual(self.record_path.read_bytes(), before)
        for ref in ("../outside.md", "C:/outside.md", "a/../README.md"):
            self.record["contracts"] = [ref]
            self.save()
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                d.guard(self.root, "sample")

    def test_selected_task_cannot_borrow_another_tasks_execution_readiness(self):
        self.start_two_tasks()
        self.record["tasks"][1].update({"depends_on": [], "state": "READY"})
        self.approve(["T01"])
        self.assertTrue(d.guard(self.root, "sample")["execution_ready"])
        self.assertTrue(d.guard(self.root, "sample", "T01")["execution_ready"])
        denied = d.guard(self.root, "sample", "T02")
        self.assertTrue(denied["record_valid"])
        self.assertFalse(denied["execution_ready"])
        self.assertEqual(denied["selected_task"], "T02")
        self.assertEqual(denied["next_tasks"], ["T01"])

    def test_selected_task_respects_dependencies_limits_and_terminal_states(self):
        self.start_two_tasks()
        self.approve(["T01", "T02"])
        self.assertFalse(d.guard(self.root, "sample", "T02")["execution_ready"])
        self.finish_task("T01")
        self.assertFalse(d.guard(self.root, "sample", "T01")["execution_ready"])
        self.record["tasks"][1]["state"] = "VERIFYING"
        self.record["tasks"][1]["used_minutes"] = 59
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T02")["execution_ready"])
        self.record["tasks"][1]["used_minutes"] = 60
        self.save()
        self.assertFalse(d.guard(self.root, "sample", "T02")["execution_ready"])
        self.assertEqual(d.read_json(self.record_path)["tasks"][1]["used_minutes"], 60)
        with self.assertRaisesRegex(ValueError, "Unknown task"):
            d.guard(self.root, "sample", "T99")

    def test_task_cli_fails_on_denial_but_generic_draft_remains_read_only(self):
        self.start_two_tasks()
        before = self.record_path.read_bytes()
        for args, expected in (([], 0), (["--task", "T01"], 1), (["--task", "T99"], 2)):
            with self.subTest(args=args):
                process = subprocess.run([sys.executable, str(SCRIPT), "guard", "--project",
                    str(self.root), "--id", "sample", *args], capture_output=True,
                    text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
                self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
                json.loads(process.stdout)
                self.assertEqual(self.record_path.read_bytes(), before)
        self.approve(["T01"])
        process = subprocess.run([sys.executable, str(SCRIPT), "guard", "--project",
            str(self.root), "--id", "sample", "--task", "T01"], capture_output=True,
            text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["execution_ready"])

    def test_module_batches_preserve_done_and_require_final_integration(self):
        self.start_two_tasks()
        integration = copy.deepcopy(self.record["tasks"][1])
        integration.update({"id": "T03", "title": "Module integration regression",
                            "depends_on": ["T01", "T02"], "checks": [self.check_def("C4")]})
        self.record["tasks"].append(integration)
        self.approve(["T01"])
        baseline = d.guard(self.root, "sample")["baseline"]
        self.finish_task("T01")
        first = d.guard(self.root, "sample")
        self.assertTrue(first["batch_complete"])
        self.assertFalse(first["delivery_ready"])
        self.assertEqual(first["remaining_tasks"], ["T02", "T03"])
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.record["tasks"][1]["state"] = "READY"
        self.approve(["T02", "T03"])
        self.assertEqual(d.guard(self.root, "sample")["baseline"], baseline)
        self.assertTrue(d.guard(self.root, "sample", "T02")["execution_ready"])
        self.assertFalse(d.guard(self.root, "sample", "T03")["execution_ready"])
        self.finish_task("T02")
        self.assertFalse(d.guard(self.root, "sample")["batch_complete"])
        self.record["tasks"][2]["state"] = "READY"
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T03")["execution_ready"])
        self.finish_task("T03")
        self.assertTrue(d.guard(self.root, "sample")["batch_complete"])
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.accept()
        result = d.guard(self.root, "sample")
        self.assertTrue(result["delivery_ready"])
        self.assertEqual(result["remaining_tasks"], [])

    def start_features(self):
        self.start()
        (self.root / "design.md").write_text("# Architecture and detailed design\n", encoding="utf-8")
        self.record.update({"scenario": "feature", "contracts": ["design.md"], "features": [
            {"id": "F01", "title": "Products", "depends_on": [], "checks": [self.check_def("FC1")]},
            {"id": "F02", "title": "Orders", "depends_on": ["F01"], "checks": [self.check_def("FC2")]}]})
        template = copy.deepcopy(self.record["tasks"][0])
        self.record["tasks"] = []
        for i, cid in enumerate(("C1", "C3", "C4", "C5"), 1):
            task = copy.deepcopy(template)
            task.update({"id": f"T{i:02}", "title": f"Task {i}", "feature": "F01" if i <= 2 else "F02",
                         "depends_on": [f"T{i-1:02}"] if i > 1 else [],
                         "state": "PENDING" if i > 1 else "READY", "checks": [self.check_def(cid)]})
            self.record["tasks"].append(task)
        self.save()

    def finish_first_feature(self):
        self.finish_task("T01")
        self.finish_task("T02")
        self.evidence("FC1")

    def test_simple_and_standard_task_limits_apply_to_the_whole_graph(self):
        self.start()
        template = copy.deepcopy(self.record["tasks"][0])
        for scenario, limit in (("simple", 3), ("standard", 15)):
            with self.subTest(scenario=scenario):
                self.record["scenario"] = scenario
                self.record["tasks"] = []
                for i in range(limit):
                    t = copy.deepcopy(template)
                    t.update({"id": f"T{i:02}", "checks": [self.check_def(f"A{i}")]})
                    self.record["tasks"].append(t)
                self.approve([t["id"] for t in self.record["tasks"]])
                self.assertTrue(d.guard(self.root, "sample")["execution_ready"])
                extra = copy.deepcopy(template)
                extra.update({"id": "EXTRA", "state": "PENDING", "checks": [self.check_def("EXTRA-C")]})
                self.record["tasks"].append(extra)
                self.save()
                rejected = d.guard(self.root, "sample")
                self.assertIn("TASK_LIMIT", self.codes(rejected))
                self.assertFalse(rejected["delivery_ready"])
                # Completed and unapproved tasks still count; a new batch cannot hide them.
                self.record["tasks"][0]["state"] = "DONE"
                self.record["approval"]["tasks"] = ["EXTRA"]
                self.save()
                self.assertIn("TASK_LIMIT", self.codes(d.guard(self.root, "sample")))

    def test_feature_limit_is_per_feature_not_per_project(self):
        self.start_features()
        self.record["features"][1]["depends_on"] = []
        template = copy.deepcopy(self.record["tasks"][0])
        self.record["tasks"] = []
        for fid in ("F01", "F02"):
            for i in range(30):
                t = copy.deepcopy(template)
                t.update({"id": f"{fid}T{i}", "feature": fid, "checks": [self.check_def(f"{fid}C{i}")]})
                self.record["tasks"].append(t)
        self.approve([t["id"] for t in self.record["tasks"]])
        result = d.guard(self.root, "sample", feature_ids=["F01", "F02"])
        self.assertTrue(result["execution_ready"])
        self.assertEqual(len(result["next_tasks"]), 30)
        extra = copy.deepcopy(self.record["tasks"][0])
        extra.update({"id": "EXTRA", "checks": [self.check_def("EXTRA-C")]})
        self.record["tasks"].append(extra)
        self.save()
        self.assertIn("TASK_LIMIT", self.codes(d.guard(self.root, "sample")))

    def test_new_scenarios_always_need_explicit_current_approval(self):
        self.start_features()
        for decision in ("PENDING", "CHANGES_REQUESTED", "REJECTED"):
            self.record["approval"]["decision"] = decision
            self.save()
            result = d.guard(self.root, "sample", "T01", ["F01"])
            self.assertFalse(result["execution_ready"])
            self.assertFalse(result["selection_ready"])
        self.record["scenario"] = "simple"
        del self.record["features"]
        self.record["tasks"] = self.record["tasks"][:1]
        del self.record["tasks"][0]["feature"]
        self.save()
        self.assertFalse(d.guard(self.root, "sample", "T01")["execution_ready"])

    def test_feature_accepts_one_detailed_design_at_custom_or_run_input_path(self):
        self.start_features()
        for path in ("uploads/商城详细设计.md", ".delivery/runs/sample/inputs/商城详细设计.md"):
            with self.subTest(path=path):
                design = self.root / path
                design.parent.mkdir(parents=True, exist_ok=True)
                design.write_text("# 商城详细设计\n商品、订单和支付的接口与验收。\n", encoding="utf-8")
                self.record["contracts"] = [path]
                self.approve(["T01", "T02", "T03", "T04"])
                result = d.guard(self.root, "sample", "T01", ["F01"])
                self.assertTrue(result["record_valid"], result["issues"])
                self.assertTrue(result["execution_ready"], result["waiting"])
                design.write_text("# 修订后的商城详细设计\n", encoding="utf-8")
                changed = d.guard(self.root, "sample", "T01", ["F01"])
                self.assertNotEqual(result["baseline"], changed["baseline"])
                self.assertFalse(changed["execution_ready"])

    def test_feature_design_and_module_acceptance_cannot_be_omitted(self):
        self.start_features()
        self.approve(["T01", "T02", "T03", "T04"])
        self.record["contracts"] = []
        self.approve(["T01", "T02", "T03", "T04"])
        self.assertFalse(d.guard(self.root, "sample", feature_ids=["F01"])["selection_ready"])
        self.record["contracts"] = ["design.md"]
        self.record["features"][0]["checks"] = []
        self.approve(["T01", "T02", "T03", "T04"])
        self.assertFalse(d.guard(self.root, "sample", feature_ids=["F01"])["execution_ready"])

    def test_feature_execution_requires_selection_and_does_not_write_records(self):
        self.start_features()
        self.approve(["T01", "T02", "T03", "T04"])
        before = self.record_path.read_bytes(), self.plan.read_bytes()
        self.assertFalse(d.guard(self.root, "sample", "T01")["execution_ready"])
        selected = d.guard(self.root, "sample", "T01", ["F01"])
        self.assertTrue(selected["execution_ready"])
        self.assertEqual(selected["next_tasks"], ["T01"])
        self.assertEqual(before, (self.record_path.read_bytes(), self.plan.read_bytes()))
        for selection in ([], ["UNKNOWN"], ["F01", "F01"]):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                d.guard(self.root, "sample", feature_ids=selection)

    def test_multi_feature_selection_orders_prerequisites_without_expanding_scope(self):
        self.start_features()
        self.approve(["T01", "T02", "T03", "T04"])
        missing = d.guard(self.root, "sample", feature_ids=["F02"])
        self.assertIn("FEATURE_SELECTION", self.codes(missing))
        self.assertFalse(missing["execution_ready"])
        selected = d.guard(self.root, "sample", feature_ids=["F02", "F01"])
        self.assertEqual(selected["selected_features"], ["F02", "F01"])
        self.assertEqual(selected["feature_order"], ["F01", "F02"])
        self.assertTrue(selected["selection_ready"])
        self.assertEqual(selected["next_tasks"], ["T01"])
        self.assertFalse(d.guard(self.root, "sample", "T03", ["F01"])["execution_ready"])

    def test_multi_selection_keeps_independent_features_serial_and_scoped(self):
        self.start_features()
        self.record["features"][1]["depends_on"] = []
        self.record["tasks"][2].update({"depends_on": [], "state": "READY"})
        self.approve(["T01", "T02", "T03", "T04"])
        self.assertFalse(d.guard(self.root, "sample", "T03", ["F01", "F02"])["execution_ready"])
        self.assertTrue(d.guard(self.root, "sample", "T03", ["F02"])["execution_ready"])
        self.assertFalse(d.guard(self.root, "sample", "T01", ["F02"])["execution_ready"])
        self.record["tasks"][2]["state"] = "RUNNING"
        self.save()
        self.assertIn("FEATURE_SELECTION", self.codes(d.guard(self.root, "sample", feature_ids=["F01", "F02"])))

    def test_selection_does_not_grant_unapproved_feature_tasks(self):
        self.start_features()
        self.approve(["T01"])
        result = d.guard(self.root, "sample", feature_ids=["F01"])
        self.assertIn("FEATURE_SELECTION", self.codes(result))
        self.assertFalse(result["selection_ready"])
        self.assertFalse(result["delivery_ready"])

    def test_feature_prerequisite_gates_tasks_without_a_direct_task_edge(self):
        self.start_features()
        self.record["tasks"][2]["depends_on"] = []
        self.approve(["T01", "T02", "T03", "T04"])
        self.assertFalse(d.guard(self.root, "sample", "T03", ["F01", "F02"])["execution_ready"])
        self.record["tasks"][2]["state"] = "RUNNING"
        self.save()
        result = d.guard(self.root, "sample", feature_ids=["F01", "F02"])
        self.assertIn("EXECUTION_GATE", self.codes(result))
        self.assertFalse(result["execution_ready"])

    def test_each_feature_runs_multiple_tasks_then_module_and_overall_acceptance(self):
        self.start_features()
        self.approve(["T01", "T02", "T03", "T04"])
        baseline = d.guard(self.root, "sample")["baseline"]
        self.assertTrue(d.guard(self.root, "sample", "T01", ["F01", "F02"])["execution_ready"])
        self.finish_task("T01")
        self.record["tasks"][1]["state"] = "READY"
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T02", ["F01", "F02"])["execution_ready"])
        self.finish_task("T02")
        pending = d.guard(self.root, "sample", feature_ids=["F01", "F02"])
        self.assertTrue(pending["features"][0]["tasks_done"])
        self.assertFalse(pending["features"][0]["complete"])
        self.assertFalse(pending["execution_ready"])
        self.evidence("FC1")
        self.assertTrue(d.guard(self.root, "sample", feature_ids=["F01"])["selection_complete"])
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.record["tasks"][2]["state"] = "READY"
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T03", ["F02"])["execution_ready"])
        self.finish_task("T03")
        self.record["tasks"][3]["state"] = "READY"
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T04", ["F02"])["execution_ready"])
        self.finish_task("T04")
        self.accept()
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.evidence("FC2")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.receive()
        complete = d.guard(self.root, "sample", feature_ids=["F01", "F02"])
        self.assertTrue(complete["selection_complete"])
        self.assertTrue(complete["delivery_ready"])
        self.assertEqual(complete["next_tasks"], [])
        self.assertEqual(complete["baseline"], baseline)
        self.evidence("FC1", "FAIL")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])

    def test_historical_feature_done_survives_batch_switch_and_resume_keeps_usage(self):
        self.start_features()
        self.approve(["T01", "T02"])
        self.finish_first_feature()
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.record["tasks"][2].update({"state": "REPAIRING", "repairs": 1, "used_minutes": 17})
        self.approve(["T03", "T04"])
        result = d.guard(self.root, "sample", "T03", ["F02"])
        self.assertTrue(result["execution_ready"])
        self.assertTrue(result["features"][0]["complete"])
        self.assertEqual((self.record["tasks"][2]["repairs"], self.record["tasks"][2]["used_minutes"]), (1, 17))
        # A narrower invocation cannot abandon recorded active work in another Feature.
        self.assertIn("FEATURE_SELECTION", self.codes(d.guard(self.root, "sample", feature_ids=["F01"])))

    def test_historical_feature_time_overrun_blocks_dependent_feature(self):
        self.start_features()
        self.approve(["T01", "T02"])
        self.finish_first_feature()
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.record["tasks"][2]["state"] = "READY"
        self.approve(["T03", "T04"])
        self.record["tasks"][0]["used_minutes"] = 61
        self.save()
        result = d.guard(self.root, "sample", "T03", ["F02"])
        self.assertIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["selection_ready"])
        self.assertFalse(result["features"][0]["complete"])
        self.assertFalse(result["delivery_ready"])
        self.record["tasks"][0]["used_minutes"] = 60
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T03", ["F02"])["execution_ready"])

    def test_feature_definition_membership_and_design_changes_invalidate_approval(self):
        self.start_features()
        self.approve(["T01", "T02", "T03", "T04"])
        approved = copy.deepcopy(self.record)
        for change in ("title", "membership", "check", "design", "scenario"):
            with self.subTest(change=change):
                self.record = copy.deepcopy(approved)
                (self.root / "design.md").write_text("# Architecture and detailed design\n", encoding="utf-8")
                if change == "title":
                    self.record["features"][0]["title"] = "Revised products"
                elif change == "membership":
                    self.record["tasks"][1]["feature"] = "F02"
                elif change == "check":
                    self.record["features"][0]["checks"][0]["expected"] = "New module contract"
                elif change == "scenario":
                    self.record.update({"scenario": "standard", "features": []})
                    for t in self.record["tasks"]:
                        t.pop("feature")
                else:
                    (self.root / "design.md").write_text("Changed architecture\n", encoding="utf-8")
                self.save()
                result = d.guard(self.root, "sample")
                old_baseline = {k: approved["approval"][k] for k in ("plan_sha256", "graph_sha256")}
                self.assertNotEqual(result["baseline"], old_baseline)
                self.assertFalse(result["execution_ready"])

    def test_feature_graph_rejects_missing_membership_dependencies_and_cycles(self):
        self.start_features()
        draft = copy.deepcopy(self.record)
        for kind in ("missing", "unknown", "cross", "cycle", "empty", "duplicate"):
            with self.subTest(kind=kind):
                self.record = copy.deepcopy(draft)
                if kind == "missing":
                    self.record["tasks"][0].pop("feature")
                elif kind == "unknown":
                    self.record["features"][0]["depends_on"] = ["MISSING"]
                elif kind == "cross":
                    self.record["features"][1]["depends_on"] = []
                elif kind == "cycle":
                    self.record["features"][0]["depends_on"] = ["F02"]
                elif kind == "empty":
                    self.record["features"].append({"id": "F03", "title": "Empty", "depends_on": [],
                                                    "checks": [self.check_def("FC3")]})
                else:
                    self.record["features"].append(copy.deepcopy(self.record["features"][0]))
                self.save()
                self.assertFalse(d.guard(self.root, "sample")["record_valid"])

    def test_feature_cli_requires_approval_and_selection_then_checks_specific_task(self):
        self.start_features()
        def cli(*extra):
            p = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "guard", "--project",
                                str(self.root), "--id", "sample", *extra],
                               capture_output=True, text=True, encoding="utf-8")
            return p.returncode, json.loads(p.stdout)
        self.assertEqual(cli("--features", "F01")[0], 1)
        self.approve(["T01", "T02", "T03", "T04"])
        self.assertEqual(cli("--task", "T01")[0], 1)
        code, result = cli("--features", "F02", "F01", "--task", "T01")
        self.assertEqual(code, 0)
        self.assertTrue(result["execution_ready"])
        self.assertEqual(cli("--features", "F01", "--task", "T03")[0], 1)
        self.assertEqual(cli("--features", "UNKNOWN")[0], 2)

    def test_two_skill_upgrade_adds_entries_without_touching_approval_or_knowledge(self):
        self.complete()
        snapshot = self.plan.read_bytes(), self.record_path.read_bytes()
        receipt_path = self.root / ".delivery/install.json"
        receipt = d.read_json(receipt_path)
        for name in ("delivery-run", "delivery-feature", "delivery-feature-run"):
            receipt["companions"].pop(name)
            shutil.rmtree(self.root / ".agents/skills" / name)
        receipt_path.write_bytes(d.packed(receipt))
        self.assertEqual(d.check(self.root)["status"], "CONFLICT")
        d.initialize(self.root)
        self.assertEqual(d.check(self.root)["status"], "CONFIGURED")
        self.assertEqual(snapshot, (self.plan.read_bytes(), self.record_path.read_bytes()))
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_new_companion_conflict_aborts_full_upgrade_preflight(self):
        d.initialize(self.root)
        target = self.root / ".agents/skills/delivery-feature-run/SKILL.md"
        target.write_text("Human customization", encoding="utf-8")
        missing = self.root / ".agents/skills/delivery-run/SKILL.md"
        missing.unlink()
        before = (self.root / ".delivery/install.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "Local edit/conflict"):
            d.initialize(self.root)
        self.assertFalse(missing.exists())
        self.assertEqual(before, (self.root / ".delivery/install.json").read_bytes())

    def test_legacy_done_history_without_scenario_is_not_rewritten_on_upgrade(self):
        self.start_two_tasks()
        self.record.pop("scenario")
        self.approve(["T01"])
        self.finish_task("T01")
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.approve(["T02"])
        self.finish_task("T02")
        self.accept()
        before = self.record_path.read_bytes()
        baseline = d.guard(self.root, "sample")["baseline"]
        d.initialize(self.root)
        result = d.guard(self.root, "sample")
        self.assertTrue(result["delivery_ready"])
        self.assertEqual(result["baseline"], baseline)
        self.assertEqual(self.record_path.read_bytes(), before)

    def test_feature_done_without_authorization_still_blocks_delivery(self):
        self.start_features()
        self.approve(["T01"])
        self.finish_first_feature()
        result = d.guard(self.root, "sample")
        self.assertIn("DONE_AUTHORIZATION", self.codes(result))
        self.assertFalse(result["delivery_ready"])
        self.assertFalse(result["features"][0]["complete"])

    def test_nonfeature_plan_cannot_use_feature_selection(self):
        self.start()
        self.approve()
        with self.assertRaises(ValueError):
            d.guard(self.root, "sample", feature_ids=["F01"])

    def test_new_cli_declares_each_scenario_without_granting_approval(self):
        d.initialize(self.root)
        for scenario in ("simple", "standard", "feature"):
            with self.subTest(scenario=scenario):
                process = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "new", "--project",
                    str(self.root), "--id", scenario, "--title", "Draft", "--scenario", scenario],
                    capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                _, path = d.run_paths(self.root, scenario)
                self.assertEqual(d.read_json(path)["scenario"], scenario)
                result = d.guard(self.root, scenario)
                self.assertTrue(result["record_valid"])
                self.assertFalse(result["execution_ready"])


    def test_receipt_binds_changed_dependencies_even_when_subjects_omit_them(self):
        self.start_git()
        dependency = self.root / "extra.py"
        dependency.write_text("value = 1\n", encoding="utf-8")
        self.record["tasks"][0]["paths"].append("extra.py")
        self.approve()
        self.record["approval"]["paths"] = ["."]
        self.save()
        self.finish_task("T01")
        self.accept()
        receipt = self.record["overall"]["accepted_sha256"]
        dependency.write_text("value = 999\n", encoding="utf-8")
        result = d.guard(self.root, "sample")
        self.assertTrue(result["record_valid"], result["issues"])
        self.assertEqual(result["change_scope"]["status"], "PASS")
        self.assertNotEqual(result["acceptance_sha256"], receipt)
        self.assertFalse(result["delivery_ready"])
        self.assertEqual(d.read_json(self.record_path)["overall"]["accepted_sha256"], receipt)

    def test_handoff_rejects_mutable_record_self_reference(self):
        self.complete()
        for field in ("artifacts", "docs"):
            original = self.record["handoff"][field][:]
            for ref in ([self.record_path.relative_to(self.root).as_posix()]
                        + ([self.record_path.relative_to(self.root).as_posix().upper()] if os.name == "nt" else [])):
                with self.subTest(field=field, ref=ref):
                    self.record["handoff"][field] = [ref]
                    self.save()
                    result = d.guard(self.root, "sample")
                    self.assertIn("SELF_REFERENCE", self.codes(result))
                    self.assertIsNone(result["acceptance_sha256"])
                    self.assertFalse(result["delivery_ready"])
            self.record["handoff"][field] = original
        self.save()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_new_run_second_write_failure_is_retryable(self):
        d.initialize(self.root)
        original = d.write_atomic

        def fail_record(path, data):
            if path.name == "record.json":
                raise OSError("Injected record write failure")
            original(path, data)

        with mock.patch.object(d, "write_atomic", side_effect=fail_record):
            with self.assertRaises(OSError):
                d.new_run(self.root, "retry", "Retry draft")
        plan, record = d.run_paths(self.root, "retry")
        self.assertFalse(plan.exists())
        self.assertFalse(record.exists())
        d.new_run(self.root, "retry", "Retry draft")
        self.assertEqual(d.read_json(record)["approval"]["decision"], "PENDING")

    def test_new_run_partial_pair_diagnosis_preserves_user_plan(self):
        d.initialize(self.root)
        plan, record = d.run_paths(self.root, "partial")
        plan.parent.mkdir(parents=True)
        plan.write_text("Human-authored plan", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Incomplete run.*plan.md.*record.json"):
            d.new_run(self.root, "partial", "Do not overwrite")
        self.assertEqual(plan.read_text(encoding="utf-8"), "Human-authored plan")
        self.assertFalse(record.exists())

    def test_inspection_consumes_a_global_streaming_budget(self):
        consumed = []

        def entries():
            for i in range(5000):
                consumed.append(i)
                entry = mock.Mock()
                entry.name = f"entry-{i}"
                yield entry

        stream = mock.MagicMock()
        stream.__enter__.return_value = entries()
        with mock.patch.object(d.os, "scandir", return_value=stream), \
                mock.patch.object(Path, "iterdir", side_effect=AssertionError("Unbounded listdir")):
            result = d.inspect(self.root)
        self.assertEqual(len(consumed), 1001)
        self.assertTrue(result["truncated"])

    def test_receipt_ignores_staging_but_binds_dependency_deletion_and_rename(self):
        self.start_git()
        extra = self.root / "extra.py"
        renamed = self.root / "renamed.py"
        extra.write_text("value = 1\n", encoding="utf-8")
        self.record["tasks"][0]["paths"] += ["extra.py", "renamed.py"]
        self.approve()
        self.record["approval"]["paths"] = ["."]
        self.save()
        self.finish_task("T01")
        self.accept()
        receipt = self.record["overall"]["accepted_sha256"]
        for action in (lambda: self.git("add", "extra.py"), lambda: self.git("reset", "--", "extra.py")):
            action()
            result = d.guard(self.root, "sample")
            self.assertEqual(result["acceptance_sha256"], receipt)
            self.assertTrue(result["delivery_ready"], result["issues"])
        extra.rename(renamed)
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        renamed.rename(extra)
        extra.unlink()
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        extra.write_text("value = 1\n", encoding="utf-8")
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])

    def test_receipt_ignores_preexisting_staged_content_and_binds_its_later_restore(self):
        self.git("init", "--quiet")
        self.git("add", "src.py", "README.md")
        self.git("commit", "--quiet", "-m", "Fixture baseline")
        readme = self.root / "README.md"
        original = readme.read_bytes()
        readme.write_text("Initial dirty content", encoding="utf-8")
        self.git("add", "README.md")
        self.start_git()
        self.finish_task("T01")
        self.accept()
        receipt = self.record["overall"]["accepted_sha256"]
        self.git("reset", "--", "README.md")
        self.assertEqual(d.guard(self.root, "sample")["acceptance_sha256"], receipt)
        readme.write_bytes(original)
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])

    def test_evidence_cannot_reference_mutable_record_as_report_or_subject(self):
        self.complete()
        for field in ("report", "subjects"):
            with self.subTest(field=field):
                original = copy.deepcopy(self.record["evidence"][-1][field])
                ref = {"path": self.record_path.relative_to(self.root).as_posix(), "sha256": "0" * 64}
                self.record["evidence"][-1][field] = ref if field == "report" else [ref]
                self.save()
                result = d.guard(self.root, "sample")
                self.assertIn("SELF_REFERENCE", self.codes(result))
                self.assertFalse(result["delivery_ready"])
                self.record["evidence"][-1][field] = original

    def test_new_run_failure_preserves_concurrently_edited_plan(self):
        d.initialize(self.root)
        plan, record = d.run_paths(self.root, "edited")
        original = d.write_atomic

        def fail_after_edit(path, data):
            if path == record:
                plan.write_text("User changed the draft", encoding="utf-8")
                raise OSError("Injected failure after an edit")
            original(path, data)

        with mock.patch.object(d, "write_atomic", side_effect=fail_after_edit):
            with self.assertRaises(OSError):
                d.new_run(self.root, "edited", "Draft")
        self.assertEqual(plan.read_text(encoding="utf-8"), "User changed the draft")
        self.assertFalse(record.exists())

    def test_new_run_diagnoses_record_only_without_overwriting_it(self):
        d.initialize(self.root)
        plan, record = d.run_paths(self.root, "record-only")
        record.parent.mkdir(parents=True)
        record.write_bytes(b'{"human": "preserve"}')
        with self.assertRaisesRegex(ValueError, "Incomplete run"):
            d.new_run(self.root, "record-only", "Draft")
        self.assertEqual(record.read_bytes(), b'{"human": "preserve"}')
        self.assertFalse(plan.exists())

    def test_inspection_budget_is_shared_across_directories_and_excluded_entries(self):
        child = self.root / "nested"
        child.mkdir()
        consumed = []

        def stream(folder):
            names = ["nested", "README.md"] if Path(folder) == self.root else ["node_modules"] * 1200

            def entries():
                for name in names:
                    consumed.append(name)
                    entry = mock.Mock()
                    entry.name = name
                    yield entry

            context = mock.MagicMock()
            context.__enter__.return_value = entries()
            return context

        with mock.patch.object(d.os, "scandir", side_effect=stream):
            result = d.inspect(self.root)
        self.assertEqual(len(consumed), 1001)
        self.assertTrue(result["truncated"])
        self.assertNotIn("README.md", result["candidates"])

    def start_git_features(self):
        for name in ("f1.py", "f2.py"):
            (self.root / name).write_text("value = 1\n", encoding="utf-8")
        self.git("init", "--quiet")
        self.git("add", "src.py", "README.md", "f1.py", "f2.py")
        self.git("commit", "--quiet", "-m", "Feature fixture baseline")
        self.start_features()
        for task in self.record["tasks"]:
            task["paths"] = ["f1.py" if task["feature"] == "F01" else "f2.py"]
            task["paths"] += [f"report-{c['id']}.txt" for c in task["checks"]]
        self.record["tasks"][1]["paths"].append("report-FC1.txt")
        self.approve(["T01", "T02", "T03", "T04"])
        self.record["approval"]["paths"] = ["."]
        self.save()

    def test_feature_checkpoint_detects_changes_to_unselected_pending_feature(self):
        self.start_git_features()
        before = d.guard(self.root, "sample", "T01", ["F01"])
        self.assertTrue(before["execution_ready"], before["issues"])
        (self.root / "f2.py").write_text("value = 2\n", encoding="utf-8")
        result = d.guard(self.root, "sample", "T01", ["F01"], before["scope_checkpoint"])
        self.assertEqual(result["change_scope"]["status"], "PASS")
        self.assertEqual(result["invocation_scope"]["outside"], ["f2.py"])
        self.assertIn("INVOCATION_SCOPE", self.codes(result))
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["delivery_ready"])

    def test_feature_checkpoint_preserves_previous_batch_but_detects_new_edits(self):
        self.start_git_features()
        (self.root / "f1.py").write_text("Prior batch implementation\n", encoding="utf-8")
        self.finish_first_feature()
        self.record["approval_history"] = [copy.deepcopy(self.record["approval"])]
        self.approve(["T03", "T04"])
        self.record["approval"]["paths"] = ["."]
        self.record["tasks"][2]["state"] = "READY"
        self.save()
        before = d.guard(self.root, "sample", "T03", ["F02"])
        self.assertTrue(before["execution_ready"], before["issues"])
        checkpoint = before["scope_checkpoint"]
        (self.root / "f2.py").write_text("Current feature implementation\n", encoding="utf-8")
        result = d.guard(self.root, "sample", "T03", ["F02"], checkpoint)
        self.assertEqual(result["invocation_scope"]["outside"], [])
        self.assertTrue(result["execution_ready"], result["issues"])
        (self.root / "f1.py").write_text("Unexpected new edit to the previous feature\n", encoding="utf-8")
        result = d.guard(self.root, "sample", "T03", ["F02"], checkpoint)
        self.assertEqual(result["invocation_scope"]["outside"], ["f1.py"])
        self.assertFalse(result["execution_ready"])

    def test_checkpoint_rejects_stale_malformed_and_wrong_selection_inputs(self):
        self.start_git_features()
        checkpoint = d.guard(self.root, "sample", "T01", ["F01"])["scope_checkpoint"]
        invalid = [{}, {**checkpoint, "features": ["F02"]}, {**checkpoint, "task": "T02"},
                   {**checkpoint, "run": "other"}, {**checkpoint, "workspace": {"head": None, "dirty": {}}},
                   {**checkpoint, "workspace": {"head": checkpoint["workspace"]["head"],
                    "dirty": {"../outside": {"worktree": None, "index": None}}}}]
        for value in invalid:
            with self.subTest(checkpoint=value):
                result = d.guard(self.root, "sample", "T01", ["F01"], value)
                self.assertIn("SCOPE_CHECKPOINT", self.codes(result))
                self.assertFalse(result["execution_ready"])
        self.plan.write_text("Changed planning baseline", encoding="utf-8")
        result = d.guard(self.root, "sample", "T01", ["F01"], checkpoint)
        self.assertIn("SCOPE_CHECKPOINT", self.codes(result))

    def test_cli_checks_actual_checkpoint_and_rejects_missing_checkpoint(self):
        self.start_git_features()
        before = d.guard(self.root, "sample", "T01", ["F01"])
        checkpoint_path = self.record_path.parent / "scope-before-T01.json"
        checkpoint_path.write_bytes(d.packed(before))
        (self.root / "f2.py").write_text("Out of invocation scope\n", encoding="utf-8")
        args = [sys.executable, "-X", "utf8", str(SCRIPT), "guard", "--project", str(self.root),
                "--id", "sample", "--task", "T01", "--features", "F01", "--changes-since",
                checkpoint_path.relative_to(self.root).as_posix()]
        process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertIn("INVOCATION_SCOPE", self.codes(json.loads(process.stdout)))
        (self.root / "f2.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / "f1.py").write_text("Current task change\n", encoding="utf-8")
        saved_checkpoint = checkpoint_path.read_bytes()
        saved_record = self.record_path.read_bytes()
        process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(json.loads(process.stdout)["invocation_scope"]["status"], "PASS")
        self.assertEqual(checkpoint_path.read_bytes(), saved_checkpoint)
        self.assertEqual(self.record_path.read_bytes(), saved_record)
        checkpoint_path.write_text("{}", encoding="utf-8")
        process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 2)
        self.assertIn("scope_checkpoint", json.loads(process.stdout)["message"])

    def invalidate_checks(self, check_ids):
        baseline = d.guard(self.root, "sample")["baseline"]
        for cid in check_ids:
            self.record["evidence"].append({"id": f"E{len(self.record['evidence'])+1}", "check": cid,
                "baseline": baseline, "method": "local sample check", "actual": "Impacted by provider repair",
                "result": "NOT_VERIFIED", "at": "2026-11-03T10:00:00+08:00", "producer": "test fixture"})
        self.save()

    def test_done_chain_repair_reopens_descendants_without_resetting_usage_or_history(self):
        self.complete_two_batches()
        self.approve(["T01", "T02"])
        history_ids = {e["id"] for e in self.record["evidence"]}
        self.record["tasks"][0].update({"state": "REPAIRING", "repairs": 1, "used_minutes": 17})
        self.record["tasks"][1]["state"] = "PENDING"
        self.save()
        self.invalidate_checks(["C1", "C3", "C2"])
        self.assertTrue(d.guard(self.root, "sample", "T01")["execution_ready"])
        self.finish_task("T01")
        self.record["tasks"][1]["state"] = "READY"
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T02")["execution_ready"])
        self.record["tasks"][1]["state"] = "DONE"
        self.save()
        self.assertIn("FALSE_DONE", self.codes(d.guard(self.root, "sample")))
        self.finish_task("T02")
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])
        self.accept()
        self.assertTrue(d.guard(self.root, "sample")["delivery_ready"])
        self.assertTrue(history_ids.issubset({e["id"] for e in self.record["evidence"]}))
        self.assertEqual((self.record["tasks"][0]["repairs"], self.record["tasks"][0]["used_minutes"]), (1, 17))

    def test_feature_repair_invalidates_downstream_module_and_overall_checks(self):
        self.start_features()
        self.approve(["T01", "T02", "T03", "T04"])
        for tid in ("T01", "T02", "T03", "T04"):
            self.finish_task(tid)
        self.evidence("FC1")
        self.evidence("FC2")
        self.accept()
        self.record["tasks"][0].update({"state": "REPAIRING", "repairs": 1})
        for task in self.record["tasks"][1:]:
            task["state"] = "PENDING"
        self.save()
        self.invalidate_checks(["C1", "C3", "C4", "C5", "FC1", "FC2", "C2"])
        result = d.guard(self.root, "sample", "T01", ["F01", "F02"])
        self.assertTrue(result["execution_ready"], result["issues"])
        for tid in ("T01", "T02"):
            self.finish_task(tid)
        self.record["tasks"][2]["state"] = "READY"
        self.save()
        self.assertFalse(d.guard(self.root, "sample", "T03", ["F02"])["execution_ready"])
        self.record["tasks"][2]["state"] = "PENDING"
        self.evidence("FC1")
        self.record["tasks"][2]["state"] = "READY"
        self.save()
        self.assertTrue(d.guard(self.root, "sample", "T03", ["F02"])["execution_ready"])
        self.assertFalse(d.guard(self.root, "sample")["delivery_ready"])

    def test_receipt_binds_worktree_content_without_staged_only_false_invalidation(self):
        self.start_git()
        self.finish_task("T01")
        self.accept()
        receipt = self.record["overall"]["accepted_sha256"]
        source = self.root / "src.py"
        original = source.read_bytes()
        source.write_text("value = 2\n", encoding="utf-8")
        self.git("add", "src.py")
        source.write_bytes(original)
        result = d.guard(self.root, "sample")
        self.assertEqual(result["acceptance_sha256"], receipt)
        self.assertTrue(result["delivery_ready"], result["issues"])

    def test_final_content_query_failure_does_not_reuse_a_receipt(self):
        self.start_git()
        self.finish_task("T01")
        self.accept()
        original = d.git_snapshot

        def unavailable_final_query(*args, **kwargs):
            if kwargs.get("content_only"):
                raise ValueError("Injected final content query failure")
            return original(*args, **kwargs)

        with mock.patch.object(d, "git_snapshot", side_effect=unavailable_final_query):
            result = d.guard(self.root, "sample")
        self.assertIn("CHANGE_SCOPE", self.codes(result))
        self.assertEqual(result["change_scope"]["status"], "NOT_VERIFIED")
        self.assertIsNone(result["acceptance_sha256"])
        self.assertFalse(result["delivery_ready"])

    def test_inspection_exact_budget_and_single_lookahead(self):
        for size in (999, 1000, 1001):
            with self.subTest(size=size):
                consumed = []

                def entries():
                    for i in range(size):
                        consumed.append(i)
                        entry = mock.Mock()
                        entry.name = f"absent-{i}"
                        yield entry

                stream = mock.MagicMock()
                stream.__enter__.return_value = entries()
                with mock.patch.object(d.os, "scandir", return_value=stream):
                    result = d.inspect(self.root)
                self.assertEqual(len(consumed), min(size, 1001))
                self.assertEqual(result["truncated"], size > 1000)

    def test_new_run_first_write_failure_leaves_no_pair(self):
        d.initialize(self.root)
        with mock.patch.object(d, "write_atomic", side_effect=OSError("Injected first write failure")):
            with self.assertRaises(OSError):
                d.new_run(self.root, "first-failure", "Draft")
        plan, record = d.run_paths(self.root, "first-failure")
        self.assertFalse(plan.exists())
        self.assertFalse(record.exists())
        d.new_run(self.root, "first-failure", "Draft")
        self.assertEqual(d.read_json(record)["approval"]["decision"], "PENDING")

    def test_new_run_failure_preserves_other_run_material(self):
        d.initialize(self.root)
        plan, record = d.run_paths(self.root, "material")
        original = d.write_atomic

        def fail_after_report(path, data):
            if path == record:
                (plan.parent / "notes.txt").write_text("Preserve other work", encoding="utf-8")
                raise OSError("Injected failure after another file appeared")
            original(path, data)

        with mock.patch.object(d, "write_atomic", side_effect=fail_after_report):
            with self.assertRaises(OSError):
                d.new_run(self.root, "material", "Draft")
        self.assertTrue(plan.exists())
        self.assertEqual((plan.parent / "notes.txt").read_text(encoding="utf-8"), "Preserve other work")


if __name__ == "__main__":
    unittest.main()
