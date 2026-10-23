#!/usr/bin/env python3
"""Project-local setup and read-only delivery record checks. Standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

VERSION = "1.0.0"
WORKFLOW = "V1.0"
SKILL = Path(__file__).resolve().parents[1]
INSTALL = ".agents/skills/delivery"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
STATES = {"PENDING", "READY", "RUNNING", "VERIFYING", "REPAIRING", "DONE",
          "BLOCKED", "NEED_DECISION", "STOPPED"}
ACTIVE = {"RUNNING", "VERIFYING", "REPAIRING"}
EXCLUDED = {".git", ".agents", ".delivery", ".venv", "venv", "node_modules",
            "__pycache__", "dist", "build", "target", ".obsidian"}
MARKERS = {"package.json", "pyproject.toml", "pom.xml", "go.mod", "Cargo.toml",
           "build.gradle", "build.gradle.kts", "Makefile", "requirements.txt"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def packed(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def count(value: object) -> bool:
    return type(value) is int and value >= 0


def linked(path: Path) -> bool:
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ) if path.exists() or path.is_symlink() else False


def safe(root: Path, relative: str) -> Path:
    if not present(relative) or "\\" in relative or ":" in relative or relative.startswith("/"):
        raise ValueError(f"Unsafe project-relative path: {relative!r}")
    parts = relative.split("/")
    if relative != "." and any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"Unsafe project-relative path: {relative!r}")
    path = root
    for index, part in enumerate(parts):
        path = path / part
        if linked(path):
            raise ValueError(f"Link/reparse point is not a managed path: {relative}")
        if index < len(parts) - 1 and path.exists() and not path.is_dir():
            raise ValueError(f"Managed parent is not a directory: {relative}")
    path.resolve().relative_to(root.resolve())
    return path


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return data


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def payload() -> dict[str, bytes]:
    files = {}
    for path in sorted(SKILL.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if linked(path):
            raise ValueError("The source Skill contains a link/reparse point")
        if path.is_file():
            files[path.relative_to(SKILL).as_posix()] = path.read_bytes()
    return files


def inspect(root: Path) -> dict:
    found, visited = [], 0

    def scan(folder: Path, depth: int) -> None:
        nonlocal visited
        for path in sorted(folder.iterdir()):
            visited += 1
            if visited > 1000:
                return
            if linked(path) or path.name in EXCLUDED:
                continue
            if path.is_file() and (path.name in MARKERS or path.name in {"AGENTS.md", "README.md"}):
                found.append(path.relative_to(root).as_posix())
            elif path.is_dir() and depth < 2:
                scan(path, depth + 1)

    scan(root, 0)
    return {"status": "INSPECTED", "candidates": found, "truncated": visited > 1000,
            "runtime_verified": False, "note": "File names only; no project command was executed."}


def initialize(root: Path) -> dict:
    source = payload()
    config_path = safe(root, ".delivery/project.json")
    receipt_path = safe(root, ".delivery/install.json")
    previous = read_json(receipt_path).get("files", {}) if receipt_path.exists() else {}
    if not isinstance(previous, dict):
        raise ValueError("Invalid install receipt; review it before upgrading")
    if set(previous) - set(source):
        raise ValueError("Upgrade removes managed files; review the old installation before continuing")
    config = read_json(config_path) if config_path.exists() else {
        "schema_version": 1, "workflow": WORKFLOW, "commands": {}, "knowledge_paths": [],
        "baseline": "NOT_VERIFIED",
        "policy": {"max_repairs": None, "max_minutes": None},
    }
    if config.get("schema_version") != 1 or config.get("workflow") != WORKFLOW:
        raise ValueError("Existing project configuration has a different schema/workflow")
    writes, unchanged = {}, []
    for relative, data in source.items():
        target = safe(root, f"{INSTALL}/{relative}")
        if target.exists():
            if not target.is_file():
                raise ValueError(f"Managed target is not a file: {relative}")
            old = target.read_bytes()
            if old == data:
                unchanged.append(relative)
                continue
            if digest(old) != previous.get(relative):
                raise ValueError(f"Local edit/conflict; nothing written: {relative}")
        writes[target] = data
    # Preflight the whole operation before writing any project file.
    if not config_path.exists():
        writes[config_path] = packed(config)
    receipt = {"schema_version": 1, "package_version": VERSION, "workflow": WORKFLOW,
               "files": {p: digest(b) for p, b in source.items()}}
    if not receipt_path.exists() or read_json(receipt_path) != receipt:
        writes[receipt_path] = packed(receipt)
    for target, data in writes.items():
        write_atomic(target, data)
    return {"status": "CONFIGURED", "written": len(writes), "unchanged": len(unchanged),
            "runtime_verified": False, "rules_modified": False,
            "note": "Project rules preserved. Configure commands and approve limits before execution."}


def check(root: Path) -> dict:
    config = read_json(safe(root, ".delivery/project.json"))
    receipt = read_json(safe(root, ".delivery/install.json"))
    issues = []
    if config.get("schema_version") != 1 or config.get("workflow") != WORKFLOW:
        issues.append("Project schema/workflow mismatch")
    if not isinstance(config.get("commands"), dict) or not isinstance(config.get("policy"), dict):
        issues.append("Project commands/policy must be objects")
    files = receipt.get("files")
    if not isinstance(files, dict) or "SKILL.md" not in files or "scripts/delivery.py" not in files:
        issues.append("Invalid install manifest")
    else:
        for relative, expected in files.items():
            path = safe(root, f"{INSTALL}/{relative}")
            if not path.is_file() or digest(path.read_bytes()) != expected:
                issues.append(f"Missing or locally changed Skill file: {relative}")
    return {"status": "CONFIGURED" if not issues else "CONFLICT", "issues": issues,
            "runtime_verified": False, "note": "Static installation check only."}


def run_paths(root: Path, run_id: str) -> tuple[Path, Path]:
    if not ID.fullmatch(run_id):
        raise ValueError("Run ID must use 1-64 letters, digits, underscores or hyphens")
    base = f".delivery/runs/{run_id}"
    return safe(root, base + "/plan.md"), safe(root, base + "/record.json")


def new_run(root: Path, run_id: str, title: str) -> dict:
    if not present(title) or any(ord(c) < 32 for c in title):
        raise ValueError("Title must be a nonempty single line")
    plan, record = run_paths(root, run_id)
    if plan.exists() or record.exists():
        raise ValueError("Run already exists; reuse it instead of overwriting")
    read_json(safe(root, ".delivery/project.json"))
    data = read_json(SKILL / "assets/run.json")
    data.update({"id": run_id, "title": title})
    text = (SKILL / "assets/delivery-plan.md").read_text(encoding="utf-8")
    text = "# " + title + "\n" + text.split("\n", 1)[1]
    write_atomic(plan, text.encode("utf-8"))
    write_atomic(record, packed(data))
    return {"status": "DRAFT", "plan": plan.relative_to(root).as_posix(),
            "record": record.relative_to(root).as_posix(), "approved": False}


def graph_digest(record: dict) -> str:
    task_keys = ("id", "title", "paths", "depends_on")
    check_keys = ("id", "kind", "trigger", "reason", "method", "expected", "failure_blocks")

    def definitions(checks: list) -> list:
        return [{key: c.get(key) for key in check_keys} for c in checks]

    graph = {"scope": record.get("scope"), "tasks": [
        {**{key: t.get(key) for key in task_keys}, "checks": definitions(t["checks"])}
        for t in record["tasks"]], "overall": definitions(record["overall"]["checks"]),
        "followups": [{k: f.get(k) for k in ("id", "goal", "method", "reason", "required_for_scope")}
                      for f in record["followups"]]}
    return digest(json.dumps(graph, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def covered(path: str, boundaries: list) -> bool:
    return any(b == "." or path == b or path.startswith(b.rstrip("/") + "/") for b in boundaries)


def guard(root: Path, run_id: str) -> dict:
    plan, path = run_paths(root, run_id)
    record = read_json(path)
    issues, waiting = [], []

    def error(code: str, field: str, message: str) -> None:
        issues.append({"code": code, "field": field, "message": message})

    def strings(value: object) -> bool:
        return isinstance(value, list) and all(present(v) for v in value)

    def project_refs(value: object, field: str, require: bool = False) -> None:
        if not strings(value) or (require and not value):
            error("REFERENCES", field, "Expected project-relative references")
            return
        for ref in value:
            if not safe(root, ref).is_file():
                error("MISSING_FILE", field, f"Reference does not exist: {ref}")

    if type(record.get("schema_version")) is not int or record["schema_version"] != 1 or record.get("id") != run_id:
        error("SCHEMA", "id", "Schema or run identity mismatch")
    for key in ("title", "scope"):
        if not present(record.get(key)):
            error("FIELD", key, "Expected nonempty text")
    for key in ("tasks", "evidence", "followups"):
        if not isinstance(record.get(key), list):
            error("TYPE", key, "Expected an array")
    for key in ("approval", "overall", "handoff"):
        if not isinstance(record.get(key), dict):
            error("TYPE", key, "Expected an object")
    if issues:
        return {"record_valid": False, "execution_ready": False, "delivery_ready": False, "issues": issues}

    tasks, checks = {}, {}
    overall = record["overall"]

    def add_checks(items: object, owner: str) -> None:
        if not isinstance(items, list):
            error("CHECKS", owner, "Expected a checks array")
            return
        if not items:
            waiting.append(f"{owner}: define required acceptance")
        for c in items:
            if not isinstance(c, dict) or not present(c.get("id")):
                error("CHECKS", owner, "Check requires an ID")
                continue
            cid = c["id"]
            if cid in checks:
                error("DUPLICATE", cid, "Duplicate check ID")
            checks[cid] = c
            if c.get("kind") not in {"REQUIRED", "CONDITIONAL", "OPTIONAL"}:
                error("CHECK_KIND", cid, "Unknown acceptance kind")
            for key in ("method", "expected"):
                if not present(c.get(key)):
                    error("CHECK_FIELD", cid, f"Missing {key}")
            if c.get("kind") == "CONDITIONAL":
                if c.get("trigger") not in {"TRIGGERED", "NOT_TRIGGERED", "UNKNOWN"}:
                    error("TRIGGER", cid, "Conditional check needs a trigger state")
                if c.get("trigger") == "NOT_TRIGGERED" and not present(c.get("reason")):
                    error("TRIGGER", cid, "Non-applicability requires a reason")
                if c.get("trigger") == "UNKNOWN":
                    waiting.append(f"{cid}: resolve conditional applicability")
            if "failure_blocks" in c and type(c["failure_blocks"]) is not bool:
                error("CHECK_FIELD", cid, "failure_blocks must be boolean")

    for task in record["tasks"]:
        if not isinstance(task, dict) or not present(task.get("id")):
            error("TASK", "tasks", "Task requires an ID")
            continue
        tid = task["id"]
        if tid in tasks:
            error("DUPLICATE", tid, "Duplicate task ID")
        tasks[tid] = task
        if task.get("state") not in STATES or not present(task.get("title")):
            error("TASK", tid, "Invalid task state/title")
        if task.get("state") in {"BLOCKED", "NEED_DECISION", "STOPPED"} and not present(task.get("note")):
            error("RESUME", tid, "Stopped/blocked tasks need a cause and next action")
        for key in ("depends_on", "paths"):
            if not strings(task.get(key)) or (key == "paths" and not task[key]):
                error("TASK", tid, f"Invalid {key}")
        for p in task.get("paths", []) if strings(task.get("paths")) else []:
            safe(root, p)
        for key in ("repairs", "used_minutes"):
            if not count(task.get(key)):
                error("USAGE", tid, f"{key} must be a nonnegative integer")
        add_checks(task.get("checks"), tid)
    add_checks(overall.get("checks"), "overall")
    seen, visiting = set(), set()

    def visit(tid: str) -> None:
        if tid in visiting:
            error("CYCLE", tid, "Task dependency cycle")
            return
        if tid in seen:
            return
        visiting.add(tid)
        for dep in tasks[tid].get("depends_on", []):
            if dep not in tasks:
                error("DEPENDENCY", tid, f"Unknown dependency: {dep}")
            else:
                visit(dep)
        visiting.remove(tid)
        seen.add(tid)

    if not issues:
        for tid in tasks:
            visit(tid)
    for f in record["followups"]:
        if not isinstance(f, dict) or f.get("required_for_scope") is not False:
            error("FOLLOWUP", "followups", "Followups must explicitly be outside current required scope")
        elif not all(present(f.get(k)) for k in ("id", "goal", "method", "reason", "resume")):
            error("FOLLOWUP", f.get("id", "followups"), "Missing goal, method, reason or resume entry")
        elif f.get("status") not in {"NOT_VERIFIED", "PASS", "FAIL"}:
            error("FOLLOWUP", f["id"], "Invalid followup status")
    if issues:
        return {"record_valid": False, "execution_ready": False, "delivery_ready": False, "issues": issues}

    baseline = {"plan_sha256": digest(plan.read_bytes()), "graph_sha256": graph_digest(record)}
    acceptance_defined = bool(tasks) and all(any(
        c["kind"] in {"REQUIRED", "CONDITIONAL"} for c in t["checks"]) for t in tasks.values())
    acceptance_defined = acceptance_defined and any(
        c["kind"] in {"REQUIRED", "CONDITIONAL"} for c in overall["checks"])
    if not acceptance_defined:
        waiting.append("Define task and overall required acceptance before execution")
    approval = record["approval"]
    approved = approval.get("decision") == "APPROVED"
    valid_approval = approved and all(present(approval.get(k)) for k in ("reviewer", "at", "source"))
    valid_approval = valid_approval and all(approval.get(k) == v for k, v in baseline.items())
    if approval.get("decision") not in {"PENDING", "APPROVED", "CHANGES_REQUESTED", "REJECTED"}:
        error("APPROVAL", "approval.decision", "Unknown approval decision")
    if not valid_approval:
        waiting.append("Approval missing, incomplete or stale")
    authorized = approval.get("tasks", [])
    boundaries = approval.get("paths", [])
    limits = approval.get("limits", {})
    if not strings(authorized) or any(t not in tasks for t in authorized):
        error("APPROVAL_SCOPE", "approval.tasks", "Unknown/invalid authorized tasks")
        authorized = []
    if not strings(boundaries):
        error("APPROVAL_SCOPE", "approval.paths", "Expected path boundaries")
        boundaries = []
    for boundary in boundaries:
        safe(root, boundary)
    if not strings(approval.get("operations", [])):
        error("APPROVAL_SCOPE", "approval.operations", "Expected allowed operations")
    if not isinstance(limits, dict):
        error("LIMITS", "approval.limits", "Expected a limits object")
        limits = {}
    repairs, minutes = limits.get("max_repairs"), limits.get("max_minutes")
    if repairs is not None and not count(repairs):
        error("LIMITS", "max_repairs", "Expected a nonnegative integer or null")
    if minutes is not None and (not count(minutes) or minutes == 0):
        error("LIMITS", "max_minutes", "Expected a positive integer or null")
    policy_ready = (count(repairs) or (count(minutes) and minutes > 0)) and not any(
        i["code"] == "LIMITS" for i in issues)
    if not policy_ready:
        waiting.append("Confirm a finite repair/time policy; null is not unlimited execution")
    if approved and (not authorized or not boundaries or not approval.get("operations")):
        error("APPROVAL_SCOPE", "approval", "Approved batch needs tasks, paths and operations")
    for tid in authorized:
        if any(not covered(p, boundaries) for p in tasks[tid]["paths"]):
            error("APPROVAL_SCOPE", tid, "Task paths exceed approved boundaries")

    # Retained batches can justify DONE, never authorize new activity.
    done_authorized = set(authorized) if valid_approval and policy_ready and not issues else set()
    history = record.get("approval_history", [])
    if not isinstance(history, list):
        error("APPROVAL_HISTORY", "approval_history", "Expected retained approval snapshots")
        history = []
    for index, prior in enumerate(history):
        field = f"approval_history[{index}]"
        if (not isinstance(prior, dict) or prior.get("decision") != "APPROVED"
                or not all(present(prior.get(k)) for k in ("reviewer", "at", "source"))
                or not all(isinstance(prior.get(k), str) and re.fullmatch(r"[a-f0-9]{64}", prior[k])
                           for k in baseline)):
            error("APPROVAL_HISTORY", field, "Expected a complete original APPROVED snapshot and source")
            continue
        if any(prior[k] != value for k, value in baseline.items()):
            continue
        prior_tasks, prior_paths = prior.get("tasks"), prior.get("paths")
        prior_operations, prior_limits = prior.get("operations"), prior.get("limits")
        if (not strings(prior_tasks) or not prior_tasks or any(t not in tasks for t in prior_tasks)
                or not strings(prior_paths) or not prior_paths
                or not strings(prior_operations) or not prior_operations
                or not isinstance(prior_limits, dict)):
            error("APPROVAL_HISTORY", field, "Retained approval needs valid tasks, paths, operations and limits")
            continue
        prior_repairs, prior_minutes = prior_limits.get("max_repairs"), prior_limits.get("max_minutes")
        if ((prior_repairs is not None and not count(prior_repairs))
                or (prior_minutes is not None and (not count(prior_minutes) or prior_minutes == 0))
                or not (count(prior_repairs) or (count(prior_minutes) and prior_minutes > 0))):
            error("APPROVAL_HISTORY", field, "Retained approval needs a valid finite repair/time policy")
            continue
        try:
            for boundary in prior_paths:
                safe(root, boundary)
        except ValueError:
            error("APPROVAL_HISTORY", field, "Unsafe retained approval path")
            continue
        if any(not covered(p, prior_paths) for tid in prior_tasks for p in tasks[tid]["paths"]):
            error("APPROVAL_HISTORY", field, "Task paths exceed retained approval boundaries")
            continue
        done_authorized.update(tid for tid in prior_tasks
                               if not count(prior_repairs) or tasks[tid]["repairs"] <= prior_repairs)

    evidence, verdicts = {}, {}
    # Old baselines and superseded attempts remain history, not current verdicts.
    latest = {e.get("check"): e.get("id") for e in record["evidence"]
              if isinstance(e, dict) and e.get("baseline") == baseline}
    for e in record["evidence"]:
        if not isinstance(e, dict) or not present(e.get("id")):
            error("EVIDENCE", "evidence", "Evidence requires an ID")
            continue
        eid, cid = e["id"], e.get("check")
        if eid in evidence:
            error("EVIDENCE", eid, "Duplicate evidence ID")
            continue
        evidence[eid] = e
        if e.get("result") not in {"PASS", "FAIL", "NOT_VERIFIED", "NOT_RUN"}:
            error("EVIDENCE", eid, "Invalid result")
        if not all(present(e.get(k)) for k in ("actual", "at", "producer", "method")):
            error("EVIDENCE", eid, "Missing actual result, timestamp, producer or method")
        ebase = e.get("baseline")
        if not isinstance(ebase, dict) or not all(
                isinstance(ebase.get(k), str) and re.fullmatch(r"[a-f0-9]{64}", ebase[k])
                for k in ("plan_sha256", "graph_sha256")):
            error("EVIDENCE_BASELINE", eid, "Evidence must identify its plan and graph")
            continue
        if ebase != baseline:
            continue
        if cid not in checks:
            error("EVIDENCE", eid, "Unknown current-baseline check")
            continue
        if e.get("method") != checks[cid]["method"]:
            error("METHOD_CHANGED", eid, "Evidence method differs from the approved check")
        if latest.get(cid) != eid:
            continue
        fresh = True
        refs = e.get("subjects")
        report = e.get("report")
        if e.get("result") in {"PASS", "FAIL"}:
            if not isinstance(refs, list) or not refs or not isinstance(report, dict):
                error("EVIDENCE", eid, "Executed results require subjects and a report")
                fresh = False
            else:
                for ref in [*refs, report]:
                    if not isinstance(ref, dict) or not present(ref.get("path")):
                        error("EVIDENCE", eid, "Invalid artifact/report reference")
                        fresh = False
                        continue
                    target = safe(root, ref["path"])
                    if not target.is_file() or digest(target.read_bytes()) != ref.get("sha256"):
                        fresh = False
                        waiting.append(f"{eid}: subject/report missing or changed")
        verdicts[cid] = e.get("result") if fresh else "NOT_VERIFIED"

    def checks_pass(items: list) -> bool:
        required = [c for c in items if c["kind"] == "REQUIRED" or (
            c["kind"] == "CONDITIONAL" and c.get("trigger") == "TRIGGERED")]
        unresolved = any(c["kind"] == "CONDITIONAL" and c.get("trigger") == "UNKNOWN" for c in items)
        optional_fail = any(c.get("failure_blocks") and verdicts.get(c["id"]) == "FAIL" for c in items)
        return bool(required) and not unresolved and not optional_fail and all(
            verdicts.get(c["id"]) == "PASS" for c in required)

    next_tasks = []
    for tid, task in tasks.items():
        deps_done = all(tasks[d]["state"] == "DONE" for d in task["depends_on"])
        if task["state"] == "DONE" and tid not in done_authorized:
            error("DONE_AUTHORIZATION", tid, "DONE requires current or retained execution approval for this baseline")
        if task["state"] == "DONE" and not checks_pass(task["checks"]):
            error("FALSE_DONE", tid, "Required current acceptance/evidence is incomplete")
        if task["state"] in ACTIVE and (not valid_approval or tid not in authorized or not deps_done):
            error("EXECUTION_GATE", tid, "Activity exceeds approval or unmet dependencies")
        if task["state"] in {"READY", *ACTIVE, "DONE"} and not deps_done:
            error("DEPENDENCY_STATE", tid, "Task state requires completed dependencies")
        over_repairs = count(repairs) and task["repairs"] > repairs
        out_of_time = count(minutes) and task["used_minutes"] >= minutes
        if tid in authorized and over_repairs:
            error("LIMIT_EXCEEDED", tid, "Recorded repairs exceed the approved maximum")
        if tid in authorized and out_of_time:
            waiting.append(f"{tid}: effective time limit reached")
        if (tid in authorized and valid_approval and policy_ready and acceptance_defined and deps_done
                and not over_repairs and not out_of_time
                and task["state"] in {"READY", *ACTIVE}):
            next_tasks.append(tid)
    if any(t["state"] == "DONE" for t in tasks.values()) and not valid_approval:
        waiting.append("Completed tasks need review against the current approved baseline")
    handoff = record["handoff"]
    if any(t["state"] in {"BLOCKED", "NEED_DECISION", "STOPPED"} for t in tasks.values()) and not present(handoff.get("resume")):
        error("RESUME", "handoff.resume", "Save a resume entry before handing off")
    project_refs(handoff.get("artifacts", []), "handoff.artifacts")
    project_refs(handoff.get("docs", []), "handoff.docs")
    knowledge = handoff.get("knowledge", {})
    if not isinstance(knowledge, dict) or knowledge.get("status") not in {
            "PENDING", "UPDATED", "NO_INCREMENT", "DRAFT_READY"}:
        error("KNOWLEDGE", "handoff.knowledge", "Invalid knowledge update status")
        knowledge = {}
    elif knowledge["status"] in {"UPDATED", "DRAFT_READY"}:
        project_refs(knowledge.get("refs"), "handoff.knowledge.refs", require=True)
    elif knowledge["status"] == "NO_INCREMENT" and not present(knowledge.get("reason")):
        error("KNOWLEDGE", "handoff.knowledge", "No-increment requires a reason")
    accepted = all(present(overall.get(k)) for k in ("accepted_by", "accepted_at", "source"))
    ready = bool(tasks) and all(t["state"] == "DONE" for t in tasks.values())
    ready = ready and checks_pass(overall["checks"]) and accepted and valid_approval and policy_ready
    ready = ready and bool(handoff.get("artifacts")) and bool(handoff.get("docs"))
    ready = ready and knowledge.get("status") in {"UPDATED", "NO_INCREMENT", "DRAFT_READY"}
    if not ready:
        waiting.append("Current-scope tasks, overall acceptance, receipt or handoff not complete")
    return {"record_valid": not issues, "execution_ready": bool(next_tasks) and not issues,
            "delivery_ready": bool(ready) and not issues, "baseline": baseline,
            "next_tasks": next_tasks, "check_results": verdicts,
            "followups_pending": [f["id"] for f in record["followups"] if f["status"] != "PASS"],
            "waiting": list(dict.fromkeys(waiting)), "issues": issues,
            "note": "Record consistency only; no command executed or human approval authenticated."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "init", "check", "new", "guard"):
        p = sub.add_parser(command)
        p.add_argument("--project", type=Path, required=True)
        if command in {"new", "guard"}:
            p.add_argument("--id", required=True)
        if command == "new":
            p.add_argument("--title", required=True)
    args = parser.parse_args()
    try:
        root = args.project.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Project must be an existing directory")
        if args.command == "new":
            result = new_run(root, args.id, args.title)
        elif args.command == "guard":
            result = guard(root, args.id)
        else:
            result = {"inspect": inspect, "init": initialize, "check": check}[args.command](root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("issues") else 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
