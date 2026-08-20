from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from supermoon36.coverage_runtime import analyze_source, discover_sources, measure


class CoverageRuntimeTests(unittest.TestCase):
    def test_analysis_discovery_measure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "sample.py"
            path.write_text('"doc"\nx=1\nif x:\n    x += 1\nelse:\n    x = 0\nfor i in range(1):\n    x += i\n', encoding="utf-8")
            model = analyze_source(path); self.assertIn(3, model.statements); self.assertIn((3, 4), model.branches)
            self.assertEqual(discover_sources((root,)), (model,))
            def runner():
                namespace = {}; exec(compile(path.read_text(), str(path), "exec"), namespace); return namespace["x"] == 2
            passed, payload = measure((model,), runner)
            self.assertTrue(passed); self.assertGreater(payload["files"][str(path.resolve())]["summary"]["covered_lines"], 0)
            self.assertIn([7, 0], payload["files"][str(path.resolve())]["executed_branches"])


if __name__ == "__main__": unittest.main()
