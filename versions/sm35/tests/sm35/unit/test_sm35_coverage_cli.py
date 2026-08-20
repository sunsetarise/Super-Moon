from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from supermoon35.cli import main
from supermoon35.coverage_runtime import TraceCollector, analyze_source, discover_sources, measure


class CoverageRuntimeTests(unittest.TestCase):
    def test_source_analysis_and_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text('"doc"\ndef choose(x):\n    if x:\n        return 1\n    return 0\n', encoding="utf-8")
            model = analyze_source(path)
            self.assertIn(3, model.statements)
            self.assertIn((3, 4), model.branches)
            self.assertEqual(discover_sources((Path(directory),)), (model,))

    def test_measure_executes_real_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text('result = 1\nif result:\n    result += 1\nelse:\n    result = 0\n', encoding="utf-8")
            model = analyze_source(path)

            def runner():
                namespace = {}
                exec(compile(path.read_text(), str(path), "exec"), namespace)
                return namespace["result"] == 2

            passed, payload = measure((model,), runner)
            self.assertTrue(passed)
            summary = payload["files"][str(path.resolve())]["summary"]
            self.assertGreater(summary["covered_lines"], 0)

    def test_cli_commands_and_required_subcommand(self):
        for command in ("status", "capabilities", "score"):
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main((command,)), 0)
            self.assertIsNotNone(json.loads(output.getvalue()))
        with self.assertRaises(SystemExit):
            main(())


if __name__ == "__main__":
    unittest.main()
