#!/usr/bin/env python3
"""Render terminal, XML, LCOV, and HTML views from SM35 coverage JSON."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("coverage", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.coverage.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    terminal = ["FILE\tSTATEMENTS\tBRANCHES"]
    lcov = []
    root = ET.Element("coverage", version="SM35-1.0")
    packages = ET.SubElement(root, "packages")
    package = ET.SubElement(packages, "package", name="supermoon34-supermoon35")
    classes = ET.SubElement(package, "classes")
    html_rows = []
    for path, row in sorted(payload["files"].items()):
        summary = row["summary"]
        statement = 100.0 if not summary["num_statements"] else 100 * summary["covered_lines"] / summary["num_statements"]
        branch = 100.0 if not summary["num_branches"] else 100 * summary["covered_branches"] / summary["num_branches"]
        terminal.append(f"{path}\t{statement:.3f}%\t{branch:.3f}%")
        class_row = ET.SubElement(classes, "class", name=Path(path).name, filename=path, line_rate=f"{statement/100:.8f}", branch_rate=f"{branch/100:.8f}")
        lines = ET.SubElement(class_row, "lines")
        executed = set(row["executed_lines"])
        for line in sorted(executed | set(row["missing_lines"])):
            ET.SubElement(lines, "line", number=str(line), hits="1" if line in executed else "0")
            lcov.extend((f"SF:{path}", f"DA:{line},{1 if line in executed else 0}"))
        lcov.append("end_of_record")
        html_rows.append(f"<tr><td>{html.escape(path)}</td><td>{statement:.3f}%</td><td>{branch:.3f}%</td></tr>")
    (args.output_dir / "coverage.txt").write_text("\n".join(terminal) + "\n")
    ET.ElementTree(root).write(args.output_dir / "coverage.xml", encoding="utf-8", xml_declaration=True)
    (args.output_dir / "coverage.lcov").write_text("\n".join(lcov) + "\n")
    page = "<!doctype html><meta charset='utf-8'><title>SM35 Coverage</title><style>body{font-family:system-ui;margin:2rem}table{border-collapse:collapse}td,th{padding:.4rem;border:1px solid #aaa}</style><h1>SM35 coverage</h1><table><tr><th>File</th><th>Statements</th><th>Branches</th></tr>" + "".join(html_rows) + "</table>"
    (args.output_dir / "index.html").write_text(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
