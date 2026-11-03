from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "index.html"


class NicDashboardRegistryTests(unittest.TestCase):
    def test_dashboard_exposes_live_specialist_registry(self):
        html = DASHBOARD.read_text(encoding="utf-8")
        self.assertIn('href="#specialists"', html)
        self.assertIn('id="specialistAgents"', html)
        self.assertIn('id="specialistMeta"', html)
        self.assertIn("data/live/nic_agent_registry.json", html)
        self.assertIn("workflow-wired roles", html)
        self.assertIn("no agent status is simulated", html)
        self.assertIn('id="operatorToolsState"', html)
        self.assertIn("/operator/capabilities", html)
        self.assertIn("bounded read-only tools", html)

    def test_dashboard_escapes_registry_values_before_rendering(self):
        html = DASHBOARD.read_text(encoding="utf-8")
        self.assertIn(".map(esc)", html)
        self.assertIn("esc(a.name||a.agent_id)", html)
        self.assertIn("esc(a.purpose||'')", html)

    def test_inline_dashboard_javascript_parses(self):
        html = DASHBOARD.read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
        self.assertTrue(scripts, "dashboard must contain its inline application script")
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
            handle.write(scripts[-1])
            handle.flush()
            result = subprocess.run(
                ["node", "--check", handle.name],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
