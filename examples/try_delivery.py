#!/usr/bin/env python3
"""Exercise the public CLI against an isolated synthetic project, then remove it."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/delivery/scripts/delivery.py"


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fingerprint(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def cli(project, command, *args, expected=0):
    process = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), command,
        "--project", str(project), *args], capture_output=True, text=True, encoding="utf-8")
    if process.returncode != expected:
        raise RuntimeError(process.stdout + process.stderr)
    return json.loads(process.stdout)


def run_demo():
    with tempfile.TemporaryDirectory(prefix="delivery-demo-") as folder:
        project = Path(folder)
        app = project / "app.py"
        app.write_text('''def normalize(value):
    return value.strip().lower()

if __name__ == "__main__":
    import sys
    print(normalize(sys.argv[1]))
''', encoding="utf-8")
        (project / "README.md").write_text(
            "# Synthetic local sample\nRun: python app.py ' Mixed '\n"
            "Hosted verification is an approved future followup in this fixture.\n", encoding="utf-8")
        cli(project, "inspect")
        cli(project, "init")
        configured = cli(project, "check")
        cli(project, "new", "--id", "sample", "--title", "Synthetic local input slice")
        path = project / ".delivery/runs/sample/record.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        method1, method2 = "local input assertions", "local command-line scenario"
        data["scope"] = "Local input normalization and handoff; no hosted deployment."
        data["tasks"] = [{"id": "T01", "title": "Local input slice", "paths": ["app.py"],
            "depends_on": [], "state": "READY", "repairs": 0, "used_minutes": 0,
            "checks": [{"id": "C1", "kind": "REQUIRED", "method": method1,
                        "expected": "Trim whitespace and normalize case; support empty input"}]}]
        data["overall"]["checks"] = [{"id": "C2", "kind": "REQUIRED", "method": method2,
            "expected": "CLI accepts input and prints the normalized result"}]
        data["followups"] = [{"id": "F01", "goal": "Hosted integration", "method": "Hosted smoke test",
            "reason": "Explicitly outside this synthetic local scope", "required_for_scope": False,
            "resume": "Provide a hosted test instance and run the documented smoke test",
            "status": "NOT_VERIFIED"}]
        save(path, data)
        draft = cli(project, "guard", "--id", "sample")
        now = datetime.now(timezone.utc).isoformat()
        # Synthetic test approval. Never use this as a real approval shortcut.
        data["approval"] = {"decision": "APPROVED", "reviewer": "SYNTHETIC FIXTURE",
            "at": now, "source": "Synthetic example only; not real human approval",
            **draft["baseline"], "tasks": ["T01"], "paths": ["app.py"], "operations": ["edit", "test"],
            "limits": {"max_repairs": 3, "max_minutes": 10}}
        save(path, data)
        approved = cli(project, "guard", "--id", "sample")
        jobs = [
            ("C1", method1, [sys.executable, "-c",
             "import app; assert app.normalize(' MiXeD ') == 'mixed'; assert app.normalize(' ') == ''"], None),
            ("C2", method2, [sys.executable, "app.py", " MiXeD "], "mixed"),
        ]
        for cid, method, command, expected in jobs:
            actual = subprocess.run(command, cwd=project, capture_output=True, text=True, encoding="utf-8")
            passed = actual.returncode == 0 and (expected is None or actual.stdout.strip() == expected)
            if not passed:
                raise AssertionError(actual.stdout + actual.stderr)
            report = project / f"report-{cid}.txt"
            report.write_text(json.dumps({"command": command, "returncode": actual.returncode,
                "stdout": actual.stdout, "stderr": actual.stderr, "expected_stdout": expected},
                ensure_ascii=False, indent=2), encoding="utf-8")
            data["evidence"].append({"id": f"E-{cid}", "check": cid, "baseline": draft["baseline"],
                "method": method, "actual": "Actual local process exited successfully and assertions matched",
                "result": "PASS", "at": now, "producer": "isolated local demo",
                "subjects": [fingerprint(app)], "report": fingerprint(report)})
        data["tasks"][0]["state"] = "DONE"
        data["overall"].update({"accepted_by": "SYNTHETIC RECEIVER", "accepted_at": now,
            "source": "Synthetic fixture receipt, not real project acceptance"})
        data["handoff"].update({"artifacts": ["app.py"], "docs": ["README.md"],
            "knowledge": {"status": "NO_INCREMENT", "reason": "Fixture README already describes the sample"}})
        save(path, data)
        complete = cli(project, "guard", "--id", "sample")
        app.write_text(app.read_text(encoding="utf-8").replace(".lower()", ""), encoding="utf-8")
        changed = cli(project, "guard", "--id", "sample", expected=1)
        return {"synthetic_fixture": True, "installation": configured["status"],
            "draft_execution_ready": draft["execution_ready"],
            "approved_execution_ready": approved["execution_ready"],
            "current_scope_delivery_ready": complete["delivery_ready"],
            "external_followups_pending": complete["followups_pending"],
            "after_source_change_delivery_ready": changed["delivery_ready"],
            "actual_local_processes": len(jobs), "temporary_project_removed_on_exit": True}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
