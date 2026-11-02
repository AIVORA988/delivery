import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_readme_flow_diagram_is_static_and_self_contained(self):
        diagram = "docs/diagrams/feature-task-loop.svg"
        for name in ("README.md", "README.en.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(diagram, text)
            self.assertNotIn("```mermaid", text)
        svg = ET.parse(ROOT / diagram).getroot()
        self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("viewBox", svg.attrib)
        for element in svg.iter():
            self.assertNotIn(element.tag.rsplit("}", 1)[-1], {"script", "foreignObject", "image"})
            for key, value in element.attrib.items():
                if key.endswith("href"):
                    self.assertTrue(value.startswith("#"))

    def test_local_document_and_image_links_resolve(self):
        for path in ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            links = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r'src="([^"]+)"', text)
            for target in links:
                if re.match(r"https?://|#", target):
                    continue
                target = target.split("#", 1)[0]
                self.assertTrue((path.parent / target).is_file(), f"{path.name}: {target}")

    def test_package_metadata_agrees_and_has_license(self):
        portable = json.loads((ROOT / "plugin.json").read_text())
        legacy = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual((portable["name"], portable["version"]), ("delivery", "1.0.0"))
        self.assertEqual((legacy["name"], legacy["version"]), ("delivery", "1.0.0"))
        self.assertEqual(legacy["skills"], "./skills/")
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text())
        text = (ROOT / "skills/delivery/SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: delivery\n"))
        self.assertIn('version: "V1.0"', text)
        self.assertNotIn("[TODO", text)
        skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
        self.assertEqual(skills, {"delivery", "delivery-run", "delivery-feature", "delivery-feature-run", "delivery-bootstrap"})

    def test_distribution_has_no_pdf_or_credentials(self):
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            self.assertNotEqual(path.suffix.lower(), ".pdf")
            if path.suffix in {".md", ".json", ".yaml", ".yml", ".svg"}:
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"github_pat_[A-Za-z0-9_]{25,}|ghp_[A-Za-z0-9]{25,}", text))
                self.assertNotIn("-----BEGIN PRIVATE KEY", text)

    def test_isolated_end_to_end_demo(self):
        result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "examples/try_delivery.py")],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["draft_execution_ready"])
        self.assertTrue(data["approved_execution_ready"])
        self.assertTrue(data["current_scope_delivery_ready"])
        self.assertEqual(data["external_followups_pending"], ["F01"])
        self.assertFalse(data["after_source_change_delivery_ready"])
        self.assertEqual(data["actual_local_processes"], 2)


if __name__ == "__main__":
    unittest.main()
