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
import subprocess
import sys
import tempfile

VERSION = "1.0.0"
WORKFLOW = "V1.0"
SKILL = Path(__file__).resolve().parents[1]
COMPANIONS = ("delivery-run", "delivery-feature", "delivery-feature-run", "delivery-bootstrap")
SCENARIOS = {"simple": 3, "standard": 15, "feature": 30}
KNOWLEDGE = "docs/knowledge"
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


def payload(folder: Path = SKILL) -> dict[str, bytes]:
    if linked(folder) or not (folder / "SKILL.md").is_file():
        raise ValueError(f"Incomplete distribution: {folder.name}/SKILL.md is required; install all five Skills")
    files = {}
    for path in sorted(folder.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if linked(path):
            raise ValueError("The source Skill contains a link/reparse point")
        if path.is_file():
            files[path.relative_to(folder).as_posix()] = path.read_bytes()
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
    sources = {name: payload(SKILL.parent / name) for name in ("delivery", *COMPANIONS)}
    config_path = safe(root, ".delivery/project.json")
    receipt_path = safe(root, ".delivery/install.json")
    previous = read_json(receipt_path) if receipt_path.exists() else {}
    companions = previous.get("companions", {})
    if not isinstance(companions, dict) or set(companions) - set(COMPANIONS):
        raise ValueError("Invalid install receipt; review it before upgrading")
    manifests = {"delivery": previous.get("files", {}),
                 **{name: companions.get(name, {}) for name in COMPANIONS}}
    config = read_json(config_path) if config_path.exists() else {
        "schema_version": 1, "workflow": WORKFLOW, "commands": {}, "knowledge_paths": [],
        "baseline": "NOT_VERIFIED",
        "policy": {"max_repairs": None, "max_minutes": None},
    }
    if config.get("schema_version") != 1 or config.get("workflow") != WORKFLOW:
        raise ValueError("Existing project configuration has a different schema/workflow")
    paths = config.get("knowledge_paths", [])
    if not isinstance(paths, list) or any(not present(p) for p in paths):
        raise ValueError("knowledge_paths must be a list of project-relative paths")
    for relative in paths:
        safe(root, relative)
    config["knowledge_paths"] = list(dict.fromkeys([*paths, KNOWLEDGE]))
    entry = safe(root, f"{KNOWLEDGE}/README.md")
    if entry.exists() and not entry.is_file():
        raise ValueError("Knowledge entry is not a file")
    writes, unchanged = {}, []
    for name, source in sources.items():
        manifest = manifests[name]
        if not isinstance(manifest, dict):
            raise ValueError("Invalid install receipt; review it before upgrading")
        if set(manifest) - set(source):
            raise ValueError("Upgrade removes managed files; review the old installation before continuing")
        for relative, data in source.items():
            target = safe(root, f".agents/skills/{name}/{relative}")
            if target.exists():
                if not target.is_file():
                    raise ValueError(f"Managed target is not a file: {name}/{relative}")
                old = target.read_bytes()
                if old == data:
                    unchanged.append(f"{name}/{relative}")
                    continue
                if digest(old) != manifest.get(relative):
                    raise ValueError(f"Local edit/conflict; nothing written: {name}/{relative}")
            writes[target] = data
    # Preflight the whole operation before writing any project file.
    if not entry.exists():
        writes[entry] = (SKILL / "assets/knowledge-index.md").read_bytes()
    if not config_path.exists() or read_json(config_path) != config:
        writes[config_path] = packed(config)
    receipt = {"schema_version": 1, "package_version": VERSION, "workflow": WORKFLOW,
               "files": {p: digest(b) for p, b in sources["delivery"].items()},
               "companions": {name: {p: digest(b) for p, b in sources[name].items()}
                              for name in COMPANIONS}}
    if not receipt_path.exists() or read_json(receipt_path) != receipt:
        writes[receipt_path] = packed(receipt)
    for target, data in writes.items():
        write_atomic(target, data)
    return {"status": "CONFIGURED", "written": len(writes), "unchanged": len(unchanged),
            "runtime_verified": False, "rules_modified": False,
            "skills": list(sources), "knowledge_entry": f"{KNOWLEDGE}/README.md",
            "note": "Knowledge entry initialized; project rules preserved. Configure commands and approve limits before execution; no business analysis performed."}


def knowledge_context(root: Path, paths: list) -> dict:
    """Bounded document discovery, not retrieval or a judgment of knowledge quality."""
    candidates, unavailable = [], []
    visited, truncated = 0, False
    template = (SKILL / "assets/knowledge-index.md").read_bytes().strip()

    def scan(path: Path, depth: int) -> None:
        nonlocal visited, truncated
        visited += 1
        if visited > 1000:
            truncated = True
            return
        try:
            if linked(path):
                unavailable.append(path.relative_to(root).as_posix())
            elif path.is_file():
                if path.suffix.lower() not in {".md", ".mdx", ".rst", ".txt"} or not path.stat().st_size:
                    return
                relative = path.relative_to(root).as_posix()
                if relative == f"{KNOWLEDGE}/README.md" and path.stat().st_size <= len(template) + 1024:
                    if path.read_bytes().strip() == template:
                        return
                if relative not in candidates and len(candidates) < 20:
                    candidates.append(relative)
            elif path.is_dir():
                if depth >= 6:
                    truncated = True
                    return
                with os.scandir(path) as entries:
                    for item in entries:
                        if item.name.startswith(".") or item.name in EXCLUDED:
                            visited += 1
                            if visited > 1000:
                                truncated = True
                                break
                            continue
                        scan(Path(item.path), depth + 1)
                        if visited > 1000:
                            break
            else:
                unavailable.append(path.relative_to(root).as_posix())
        except OSError:
            unavailable.append(path.relative_to(root).as_posix())

    for relative in dict.fromkeys(paths):
        scan(safe(root, relative), 0)
        if visited > 1000:
            break
    return {"entry": f"{KNOWLEDGE}/README.md", "paths": paths, "candidates": candidates,
            "empty": False if candidates else None if truncated or unavailable else True,
            "truncated": truncated, "unavailable": unavailable,
            "note": "Names and the default entry only; candidates are not verified knowledge."}


def check(root: Path) -> dict:
    config = read_json(safe(root, ".delivery/project.json"))
    receipt = read_json(safe(root, ".delivery/install.json"))
    issues = []
    if config.get("schema_version") != 1 or config.get("workflow") != WORKFLOW:
        issues.append("Project schema/workflow mismatch")
    if not isinstance(config.get("commands"), dict) or not isinstance(config.get("policy"), dict):
        issues.append("Project commands/policy must be objects")
    companions = receipt.get("companions", {})
    if not isinstance(companions, dict) or set(companions) - set(COMPANIONS):
        issues.append("Invalid companion manifest")
        companions = {}
    manifests = {"delivery": receipt.get("files"),
                 **{name: companions.get(name) for name in COMPANIONS}}
    for name, files in manifests.items():
        if (not isinstance(files, dict) or "SKILL.md" not in files
                or (name == "delivery" and "scripts/delivery.py" not in files)):
            issues.append(f"Incomplete {name} installation; run init from the complete distribution")
            continue
        for relative, expected in files.items():
            path = safe(root, f".agents/skills/{name}/{relative}")
            if not path.is_file() or digest(path.read_bytes()) != expected:
                issues.append(f"Missing or locally changed Skill file: {name}/{relative}")
    paths = config.get("knowledge_paths", [])
    if not isinstance(paths, list) or any(not present(p) for p in paths):
        raise ValueError("knowledge_paths must be a list of project-relative paths")
    if KNOWLEDGE not in paths or not safe(root, f"{KNOWLEDGE}/README.md").is_file():
        issues.append("Knowledge entry missing or unregistered; run init")
    for relative in paths:
        safe(root, relative)
    context = knowledge_context(root, paths)
    return {"status": "CONFIGURED" if not issues else "CONFLICT", "issues": issues,
            "knowledge": context,
            "runtime_verified": False, "note": "Static installation check only."}


def run_paths(root: Path, run_id: str) -> tuple[Path, Path]:
    if not ID.fullmatch(run_id):
        raise ValueError("Run ID must use 1-64 letters, digits, underscores or hyphens")
    base = f".delivery/runs/{run_id}"
    return safe(root, base + "/plan.md"), safe(root, base + "/record.json")


def git_snapshot(root: Path, run_id: str, head: str | None = "HEAD") -> dict | None:
    """Read Git paths and fingerprints; never stage, reset or change project files."""
    def git(*args: str, required: bool = True) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(["git", "--literal-pathspecs", "-c", "core.fsmonitor=false",
                "-C", str(root), *args], capture_output=True, timeout=30,
                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Git workspace query timed out") from exc
        if required and result.returncode:
            raise ValueError(f"Git workspace query failed: {args[0]}")
        return result

    try:
        top = git("rev-parse", "--show-toplevel", required=False)
    except FileNotFoundError:
        return None
    if top.returncode:
        if b"not a git repository" in top.stderr:
            return None
        raise ValueError("Cannot identify Git workspace; review repository access")
    prefix = root.resolve().relative_to(Path(os.fsdecode(top.stdout.rstrip(b"\r\n"))).resolve()).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    if head == "HEAD":
        commit = git("rev-parse", "--verify", "HEAD", required=False)
        head = commit.stdout.decode("ascii").strip() if not commit.returncode else None

    def relative(value: bytes) -> str:
        name = os.fsdecode(value)
        if not name.startswith(prefix):
            raise ValueError("Git returned a path outside the target project")
        return name[len(prefix):]

    index = {}
    for item in git("ls-files", "--full-name", "--stage", "-z", "--", ".").stdout.split(b"\0"):
        if item:
            fields, name = item.split(b"\t", 1)
            mode, oid, stage = fields.decode("ascii").split()
            if stage != "0":
                raise ValueError("Resolve Git conflicts before recording a workspace snapshot")
            index[relative(name)] = mode + ":" + oid
    names = set(index) if head is None else set()
    if head is not None:
        for cached in ([], ["--cached"]):
            output = git("diff", *cached, "--no-relative", "--name-only", "--no-renames", "--no-ext-diff",
                         "--no-textconv", "-z", head, "--", ".").stdout
            names.update(relative(p) for p in output.split(b"\0") if p)
    output = git("ls-files", "--full-name", "--others", "--exclude-standard", "-z", "--", ".").stdout
    names.update(relative(p) for p in output.split(b"\0") if p)
    dirty = {}
    for ref in sorted(names):
        if ref.startswith(f".delivery/runs/{run_id}/"):
            continue
        safe(root, str(Path(ref).parent).replace("\\", "/"))
        target = root / ref
        if target.is_symlink():
            fingerprint = "link:" + digest(os.fsencode(os.readlink(target)))
        else:
            target = safe(root, ref)
            if target.is_file():
                executable = bool(target.stat().st_mode & 0o111)
                fingerprint = "file:" + digest(bytes([executable]) + target.read_bytes())
            elif target.exists():
                raise ValueError(f"Changed directory/submodule needs manual review: {ref}")
            else:
                fingerprint = None
        dirty[ref] = {"worktree": fingerprint, "index": index.get(ref)}
    return {"head": head, "dirty": dirty}


def new_run(root: Path, run_id: str, title: str, scenario: str = "standard") -> dict:
    if not present(title) or any(ord(c) < 32 for c in title):
        raise ValueError("Title must be a nonempty single line")
    if scenario not in SCENARIOS:
        raise ValueError("Unknown planning scenario")
    plan, record = run_paths(root, run_id)
    if plan.exists() or record.exists():
        raise ValueError("Run already exists; reuse it instead of overwriting")
    read_json(safe(root, ".delivery/project.json"))
    data = read_json(SKILL / "assets/run.json")
    data.update({"id": run_id, "title": title, "scenario": scenario,
                 "workspace": git_snapshot(root, run_id)})
    if scenario == "feature":
        data["features"] = []
    text = (SKILL / "assets/delivery-plan.md").read_text(encoding="utf-8")
    text = "# " + title + "\n" + text.split("\n", 1)[1]
    write_atomic(plan, text.encode("utf-8"))
    write_atomic(record, packed(data))
    return {"status": "DRAFT", "plan": plan.relative_to(root).as_posix(),
            "record": record.relative_to(root).as_posix(), "approved": False}


def graph_digest(record: dict, root: Path) -> str:
    task_keys = ("id", "title", "paths", "depends_on")
    if record.get("scenario") == "feature":
        task_keys += ("feature",)
    check_keys = ("id", "kind", "trigger", "reason", "method", "expected", "failure_blocks")

    def definitions(checks: list) -> list:
        return [{key: c.get(key) for key in check_keys} for c in checks]

    graph = {"scope": record.get("scope"), "tasks": [
        {**{key: t.get(key) for key in task_keys}, "checks": definitions(t["checks"])}
        for t in record["tasks"]], "overall": definitions(record["overall"]["checks"]),
        "followups": [{k: f.get(k) for k in ("id", "goal", "method", "reason", "required_for_scope")}
                      for f in record["followups"]]}
    # Missing scenario retains historical approval hashes; new runs always declare it.
    if "scenario" in record:
        graph["scenario"] = record["scenario"]
    if record.get("scenario") == "feature":
        graph["features"] = [{"id": f["id"], "title": f["title"],
                              "depends_on": f["depends_on"], "checks": definitions(f["checks"])}
                             for f in record["features"]]
    # Omit empty contracts to preserve approvals made before contract binding existed.
    if record.get("contracts"):
        graph["contracts"] = [{"path": p, "sha256": digest(safe(root, p).read_bytes())}
                              for p in sorted(record["contracts"])]
    if record.get("workspace") is not None:
        graph["workspace"] = record["workspace"]
    return digest(json.dumps(graph, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def covered(path: str, boundaries: list) -> bool:
    return any(b == "." or path == b or path.startswith(b.rstrip("/") + "/") for b in boundaries)


def guard(root: Path, run_id: str, task_id: str | None = None,
          feature_ids: list[str] | None = None) -> dict:
    plan, path = run_paths(root, run_id)
    record = read_json(path)
    issues, waiting = [], []

    def error(code: str, field: str, message: str) -> None:
        issues.append({"code": code, "field": field, "message": message})

    def strings(value: object) -> bool:
        return isinstance(value, list) and all(present(v) for v in value)

    def project_refs(value: object, field: str, require: bool = False) -> bool:
        if not strings(value) or (require and not value):
            error("REFERENCES", field, "Expected project-relative references")
            return False
        valid = True
        for ref in value:
            if not safe(root, ref).is_file():
                error("MISSING_FILE", field, f"Reference does not exist: {ref}")
                valid = False
        return valid

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
    scenario = record.get("scenario")
    if "scenario" in record and (not isinstance(scenario, str) or scenario not in SCENARIOS):
        error("SCENARIO", "scenario", "Expected simple, standard or feature")
    if scenario != "feature" and record.get("features") not in (None, []):
        error("FEATURE", "features", "Feature definitions require the feature scenario")
    contracts = record.get("contracts", [])
    if not strings(contracts) or len(contracts) != len(set(contracts)):
        error("CONTRACTS", "contracts", "Expected unique project-relative contract files")
    else:
        for ref in contracts:
            target = safe(root, ref)
            if target == path or not target.is_file():
                error("CONTRACTS", "contracts", "Contract must exist and cannot be the mutable run record")
    workspace = record.get("workspace")
    if workspace is not None:
        if (not isinstance(workspace, dict) or set(workspace) != {"head", "dirty"}
                or (workspace.get("head") is not None and (not isinstance(workspace["head"], str)
                    or not re.fullmatch(r"[a-f0-9]{40}(?:[a-f0-9]{24})?", workspace["head"])))
                or not isinstance(workspace.get("dirty"), dict)):
            error("WORKSPACE", "workspace", "Expected the original Git head and dirty-file fingerprints")
        else:
            for ref, value in workspace["dirty"].items():
                if (not present(ref) or "\\" in ref or ":" in ref or ref.startswith("/")
                        or any(p in {"", ".", ".."} for p in ref.split("/"))
                        or not isinstance(value, dict) or set(value) != {"worktree", "index"}
                        or (value.get("worktree") is not None and (not isinstance(value["worktree"], str)
                            or not re.fullmatch(r"(?:file|link):[a-f0-9]{64}", value["worktree"])))
                        or (value.get("index") is not None and (not isinstance(value["index"], str)
                            or not re.fullmatch(r"[0-7]{6}:[a-f0-9]{40}(?:[a-f0-9]{24})?", value["index"])))):
                    error("WORKSPACE", "workspace.dirty", "Invalid original Git fingerprint")
    if issues:
        return {"record_valid": False, "execution_ready": False, "batch_complete": False,
                "delivery_ready": False, "issues": issues}

    tasks, checks, features = {}, {}, {}
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

    if scenario == "feature":
        if not isinstance(record.get("features"), list):
            error("FEATURE", "features", "Expected a Feature array")
        else:
            for f in record["features"]:
                if (not isinstance(f, dict) or not present(f.get("id"))
                        or not ID.fullmatch(f["id"]) or not present(f.get("title"))):
                    error("FEATURE", "features", "Feature requires a stable ID and title")
                    continue
                fid = f["id"]
                if fid in features:
                    error("DUPLICATE", fid, "Duplicate Feature ID")
                features[fid] = f
                if not strings(f.get("depends_on")) or len(f["depends_on"]) != len(set(f["depends_on"])):
                    error("FEATURE", fid, "Expected unique Feature dependencies")
                add_checks(f.get("checks"), fid)
    elif scenario in {"simple", "standard"} and len(record["tasks"]) > SCENARIOS[scenario]:
        error("TASK_LIMIT", "tasks", f"{scenario} allows at most {SCENARIOS[scenario]} tasks in the whole Graph")

    for task in record["tasks"]:
        if not isinstance(task, dict) or not present(task.get("id")):
            error("TASK", "tasks", "Task requires an ID")
            continue
        tid = task["id"]
        if tid in tasks:
            error("DUPLICATE", tid, "Duplicate task ID")
        tasks[tid] = task
        if scenario == "feature":
            if not present(task.get("feature")) or task["feature"] not in features:
                error("FEATURE", tid, "Task must belong to a defined Feature")
        elif task.get("feature") is not None:
            error("FEATURE", tid, "Task Feature membership requires the feature scenario")
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
        if task.get("state") == "REPAIRING" and task.get("repairs") == 0:
            error("REPAIR_STATE", tid, "Register the repair attempt before entering REPAIRING")
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
    feature_ancestors, feature_visiting = {}, set()

    def feature_visit(fid: str) -> set:
        if fid in feature_visiting:
            error("FEATURE_CYCLE", fid, "Feature dependency cycle")
            return set()
        if fid in feature_ancestors:
            return feature_ancestors[fid]
        feature_visiting.add(fid)
        ancestors = set()
        for dep in features[fid]["depends_on"]:
            if dep not in features:
                error("FEATURE_DEPENDENCY", fid, f"Unknown Feature dependency: {dep}")
            else:
                ancestors.add(dep)
                ancestors.update(feature_visit(dep))
        feature_visiting.remove(fid)
        feature_ancestors[fid] = ancestors
        return ancestors

    if not issues:
        for fid in features:
            feature_visit(fid)
            members = [t for t in tasks.values() if t.get("feature") == fid]
            if not members or len(members) > SCENARIOS["feature"]:
                error("TASK_LIMIT", fid, "Each Feature requires 1-30 tasks; completed tasks also count")
        for tid, t in tasks.items():
            for dep in t["depends_on"]:
                provider = tasks[dep].get("feature")
                if scenario == "feature" and provider != t["feature"] and provider not in feature_ancestors[t["feature"]]:
                    error("FEATURE_DEPENDENCY", tid, "Cross-Feature task dependency is missing from the Feature graph")
    for f in record["followups"]:
        if not isinstance(f, dict) or f.get("required_for_scope") is not False:
            error("FOLLOWUP", "followups", "Followups must explicitly be outside current required scope")
        elif not all(present(f.get(k)) for k in ("id", "goal", "method", "reason", "resume")):
            error("FOLLOWUP", f.get("id", "followups"), "Missing goal, method, reason or resume entry")
        elif f.get("status") not in {"NOT_VERIFIED", "PASS", "FAIL"}:
            error("FOLLOWUP", f["id"], "Invalid followup status")
    if issues:
        return {"record_valid": False, "execution_ready": False, "batch_complete": False,
                "delivery_ready": False, "issues": issues}

    if task_id is not None and task_id not in tasks:
        raise ValueError(f"Unknown task: {task_id}")
    if feature_ids is not None:
        if (scenario != "feature" or not isinstance(feature_ids, list) or not feature_ids
                or not strings(feature_ids) or len(feature_ids) != len(set(feature_ids))
                or any(fid not in features for fid in feature_ids)):
            raise ValueError("Select unique existing Feature IDs from a feature plan")
    baseline = {"plan_sha256": digest(plan.read_bytes()), "graph_sha256": graph_digest(record, root)}
    def required_checks(items: list) -> list:
        return [c for c in items if c["kind"] == "REQUIRED" or (
            c["kind"] == "CONDITIONAL" and c.get("trigger") == "TRIGGERED")]

    acceptance_defined = bool(tasks) and all(required_checks(owner["checks"])
        for owner in [*tasks.values(), overall, *features.values()])
    design_ready = scenario != "feature" or bool(contracts)
    if not design_ready:
        waiting.append("Bind the architecture and detailed design files in contracts before execution")
    acceptance_defined = acceptance_defined and design_ready
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

    def within_limits(task: dict, max_repairs: object, max_minutes: object) -> bool:
        return ((not count(max_repairs) or task["repairs"] <= max_repairs)
                and (not count(max_minutes) or task["used_minutes"] <= max_minutes))

    # Retained batches can justify DONE, never authorize new activity.
    done_authorized = ({tid for tid in authorized if within_limits(tasks[tid], repairs, minutes)}
                       if valid_approval and policy_ready and not issues else set())
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
                               if within_limits(tasks[tid], prior_repairs, prior_minutes))

    change_scope = {"status": "NOT_CONFIGURED", "changed": [], "outside": [],
                    "reason": "No original Git snapshot; review actual changes manually"}
    if workspace is not None:
        change_scope = {"status": "WAITING_APPROVAL", "changed": [], "outside": []}
        if valid_approval and not issues:
            try:
                current = git_snapshot(root, run_id, workspace["head"])
                if current is None:
                    raise ValueError("The recorded Git workspace is unavailable")
                changed = sorted(ref for ref in workspace["dirty"].keys() | current["dirty"].keys()
                                 if workspace["dirty"].get(ref) != current["dirty"].get(ref))
                allowed = [p for tid, task in tasks.items()
                           if tid in authorized or (task["state"] == "DONE" and tid in done_authorized)
                           for p in task["paths"]] + contracts
                outside = [ref for ref in changed if not covered(ref, allowed)]
                change_scope = {"status": "FAIL" if outside else "PASS", "changed": changed, "outside": outside}
                for ref in outside:
                    error("CHANGE_SCOPE", ref, "Actual Git changes exceed current or completed-task authorization")
            except (OSError, ValueError) as exc:
                change_scope = {"status": "NOT_VERIFIED", "changed": [], "outside": [], "reason": str(exc)}
                error("CHANGE_SCOPE", "workspace", "Cannot verify actual Git changes; preserve the original snapshot")

    evidence, verdicts = {}, {}
    blocking_failures = set()
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
        if e.get("result") == "FAIL" and checks[cid].get("failure_blocks"):
            blocking_failures.add(cid)
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
        if verdicts[cid] == "PASS":
            blocking_failures.discard(cid)

    def checks_pass(items: list) -> bool:
        required = required_checks(items)
        unresolved = any(c["kind"] == "CONDITIONAL" and c.get("trigger") == "UNKNOWN" for c in items)
        optional_fail = any(c["id"] in blocking_failures for c in items)
        return bool(required) and not unresolved and not optional_fail and all(
            verdicts.get(c["id"]) == "PASS" for c in required)

    feature_members = {fid: [tid for tid, t in tasks.items() if t.get("feature") == fid]
                       for fid in features}
    feature_complete = {fid: design_ready and all(tasks[tid]["state"] == "DONE" and tid in done_authorized
                                and checks_pass(tasks[tid]["checks"]) for tid in members)
                        and checks_pass(features[fid]["checks"])
                        for fid, members in feature_members.items()}
    next_tasks = []
    for tid, task in tasks.items():
        deps_done = all(tasks[d]["state"] == "DONE" for d in task["depends_on"])
        if scenario == "feature":
            deps_done = deps_done and all(feature_complete[d] for d in features[task["feature"]]["depends_on"])
        if task["state"] == "DONE" and tid not in done_authorized:
            error("DONE_AUTHORIZATION", tid, "DONE requires current or retained approval covering this baseline, scope and recorded usage")
        if task["state"] == "DONE" and not checks_pass(task["checks"]):
            error("FALSE_DONE", tid, "Required current acceptance/evidence is incomplete")
        if task["state"] in ACTIVE and (not valid_approval or tid not in authorized or not deps_done):
            error("EXECUTION_GATE", tid, "Activity exceeds approval or unmet dependencies")
        if task["state"] in {"READY", *ACTIVE, "DONE"} and not deps_done:
            error("DEPENDENCY_STATE", tid, "Task state requires completed dependencies")
        over_repairs = count(repairs) and task["repairs"] > repairs
        out_of_time = count(minutes) and task["used_minutes"] >= minutes
        if (tid in authorized and not within_limits(task, repairs, minutes)
                and (task["state"] != "DONE" or tid not in done_authorized)):
            error("LIMIT_EXCEEDED", tid, "Recorded repairs or time exceed the approved maximum")
        if tid in authorized and out_of_time and task["state"] != "DONE":
            waiting.append(f"{tid}: effective time limit reached")
        if (tid in authorized and valid_approval and policy_ready and acceptance_defined and deps_done
                and not over_repairs and not out_of_time
                and task["state"] in {"READY", *ACTIVE}):
            next_tasks.append(tid)
    feature_order = []
    if scenario == "feature":
        selected = set(feature_ids or [])

        def order_feature(fid: str) -> None:
            if fid in feature_order:
                return
            for dep in features[fid]["depends_on"]:
                if dep in selected:
                    order_feature(dep)
            feature_order.append(fid)

        for fid in feature_ids or []:
            order_feature(fid)
            if any(tid not in authorized and tasks[tid]["state"] != "DONE"
                   for tid in feature_members[fid]):
                error("FEATURE_SELECTION", fid, "Selected Feature contains tasks outside current approval")
            if any(not feature_complete[d] and d not in selected for d in features[fid]["depends_on"]):
                error("FEATURE_SELECTION", fid, "Select unfinished prerequisite Features explicitly or wait for completion")
        current_feature = next((fid for fid in feature_order if not feature_complete[fid]), None)
        for tid, task in tasks.items():
            if selected and task["state"] in ACTIVE and task["feature"] != current_feature:
                error("FEATURE_SELECTION", tid, "Finish or resolve the current Feature before starting another")
        next_tasks = [tid for tid in next_tasks if tasks[tid]["feature"] == current_feature]
        if task_id is not None and tasks[task_id]["feature"] not in selected:
            waiting.append(f"{task_id}: task is outside the selected Features")
        if not selected:
            waiting.append("Select one or more approved Features before starting or resuming tasks")
    if any(t["state"] == "DONE" for t in tasks.values()) and not valid_approval:
        waiting.append("Completed tasks need review against the current approved baseline")
    handoff = record["handoff"]
    if any(t["state"] in {"BLOCKED", "NEED_DECISION", "STOPPED"} for t in tasks.values()) and not present(handoff.get("resume")):
        error("RESUME", "handoff.resume", "Save a resume entry before handing off")
    artifacts_valid = project_refs(handoff.get("artifacts", []), "handoff.artifacts")
    docs_valid = project_refs(handoff.get("docs", []), "handoff.docs")
    knowledge = handoff.get("knowledge", {})
    if not isinstance(knowledge, dict) or knowledge.get("status") not in {
            "PENDING", "UPDATED", "NO_INCREMENT", "DRAFT_READY"}:
        error("KNOWLEDGE", "handoff.knowledge", "Invalid knowledge update status")
        knowledge = {}
    elif knowledge["status"] in {"UPDATED", "DRAFT_READY"}:
        project_refs(knowledge.get("refs"), "handoff.knowledge.refs", require=True)
    elif knowledge["status"] == "NO_INCREMENT" and not present(knowledge.get("reason")):
        error("KNOWLEDGE", "handoff.knowledge", "No-increment requires a reason")
    ready = bool(tasks) and all(t["state"] == "DONE" for t in tasks.values())
    ready = ready and checks_pass(overall["checks"]) and valid_approval and policy_ready
    ready = ready and design_ready and all(feature_complete.values()) and not issues
    ready = ready and artifacts_valid and docs_valid and bool(handoff.get("artifacts")) and bool(handoff.get("docs"))
    ready = ready and knowledge.get("status") in {"UPDATED", "NO_INCREMENT", "DRAFT_READY"}
    acceptance_sha256 = None
    if ready:
        receipt_checks = {c["id"] for c in required_checks(list(checks.values()))}
        receipt_checks.update(cid for cid, c in checks.items() if c.get("failure_blocks"))
        receipt = {"baseline": baseline,
                   "evidence": {cid: evidence.get(latest.get(cid)) for cid in sorted(receipt_checks)},
                   "files": [{"path": ref, "sha256": digest(safe(root, ref).read_bytes())}
                             for ref in sorted(set(handoff["artifacts"] + handoff["docs"]))]}
        acceptance_sha256 = digest(json.dumps(receipt, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    accepted = (all(present(overall.get(k)) for k in ("accepted_by", "accepted_at", "source"))
                and acceptance_sha256 is not None and overall.get("accepted_sha256") == acceptance_sha256)
    if acceptance_sha256 is not None and not accepted:
        waiting.append("Record actual acceptance for the current acceptance_sha256; an old receipt is not current")
    ready = ready and accepted
    if not ready:
        waiting.append("Current-scope tasks, overall acceptance, receipt or handoff not complete")
    batch_complete = valid_approval and policy_ready and bool(authorized) and all(
        tasks[tid]["state"] == "DONE" and checks_pass(tasks[tid]["checks"]) for tid in authorized)
    executable = bool(next_tasks) if task_id is None else task_id in next_tasks
    if task_id is not None and not executable:
        waiting.append(f"{task_id}: selected task is not executable in the current approved batch")
    return {"record_valid": not issues, "execution_ready": executable and not issues,
            "batch_complete": bool(batch_complete) and not issues,
            "remaining_tasks": [tid for tid, t in tasks.items() if t["state"] != "DONE"],
            **({"selected_task": task_id} if task_id is not None else {}),
            **({"selected_features": feature_ids or [], "feature_order": feature_order,
                "selection_ready": bool(feature_ids) and valid_approval and policy_ready and acceptance_defined and not issues,
                "selection_complete": bool(feature_ids) and valid_approval and policy_ready and acceptance_defined
                                      and all(feature_complete[fid] for fid in feature_ids) and not issues,
                "features": [{"id": fid, "title": f["title"], "tasks": feature_members[fid],
                              "done": sum(tasks[t]["state"] == "DONE" for t in feature_members[fid]),
                              "tasks_done": all(tasks[t]["state"] == "DONE" for t in feature_members[fid]),
                              "complete": bool(feature_complete[fid]) and not issues,
                              "authorized": valid_approval and policy_ready and not issues and all(
                                  t in authorized or (tasks[t]["state"] == "DONE" and t in done_authorized)
                                  for t in feature_members[fid]),
                              "blocked_by": [d for d in f["depends_on"] if not feature_complete[d]]}
                             for fid, f in features.items()]} if scenario == "feature" else {}),
            "delivery_ready": bool(ready) and not issues, "baseline": baseline,
            "acceptance_sha256": acceptance_sha256,
            "change_scope": change_scope,
            "next_tasks": next_tasks, "check_results": verdicts,
            "followups_pending": [f["id"] for f in record["followups"] if f["status"] != "PASS"],
            "waiting": list(dict.fromkeys(waiting)), "issues": issues,
            "note": "Record/file consistency and read-only Git queries only; no business command executed or human approval authenticated."}


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
            p.add_argument("--scenario", choices=SCENARIOS, default="standard")
        if command == "guard":
            p.add_argument("--task", help="Check execution readiness of this specific task")
            p.add_argument("--features", nargs="+", help="Explicitly selected Feature IDs for this invocation")
    args = parser.parse_args()
    try:
        root = args.project.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Project must be an existing directory")
        if args.command == "new":
            result = new_run(root, args.id, args.title, args.scenario)
        elif args.command == "guard":
            result = guard(root, args.id, args.task, args.features)
        else:
            result = {"inspect": inspect, "init": initialize, "check": check}[args.command](root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        blocked_task = args.command == "guard" and args.task is not None and not result["execution_ready"]
        blocked_selection = args.command == "guard" and args.features is not None and not result.get("selection_ready")
        return 1 if result.get("issues") or blocked_task or blocked_selection else 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
