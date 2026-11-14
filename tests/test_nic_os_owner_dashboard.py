import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class OwnerDashboardTests(unittest.TestCase):
    def test_task_controls_are_present_and_script_parses(self):
        html = Path("dashboard/owner.html").read_text(encoding="utf-8")
        self.assertIn('id="taskGoal"', html)
        self.assertIn('id="taskList"', html)
        self.assertIn('id="taskEvents"', html)
        self.assertIn('"/control/tasks"', html)
        scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
        self.assertEqual(len(scripts), 1)
        self.assertIn("async function refreshTasks()", scripts[0])
        self.assertIn("async function taskAction", scripts[0])
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is unavailable; static dashboard assertions passed")
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
            handle.write(scripts[0])
            handle.flush()
            result = subprocess.run([node, "--check", handle.name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
