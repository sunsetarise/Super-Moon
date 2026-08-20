#!/usr/bin/env python3
"""Execute CadQuery/OCCT STEP and direct-OCCT IGES qualification when installed."""

from __future__ import annotations

import argparse
from pathlib import Path

from tool_common import detect_capability, unavailable, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capability = detect_capability("cad")
    if not capability.available:
        return unavailable("cad", args.output, "CadQuery and OCP/OCCT unavailable")
    if not args.authorize:
        return unavailable("cad", args.output, "CAD translator execution requires explicit authorization")
    import cadquery as cq
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.IGESControl import IGESControl_Reader, IGESControl_Writer
    from OCP.IFSelect import IFSelect_RetDone
    args.workdir.mkdir(parents=True, exist_ok=True)
    solid = cq.Workplane("XY").box(10, 20, 30).edges().fillet(1).val()
    step = args.workdir / "reference.step"
    cq.exporters.export(solid, str(step))
    step_shape = cq.importers.importStep(str(step)).val()
    iges = args.workdir / "reference.iges"
    writer = IGESControl_Writer()
    writer.AddShape(solid.wrapped)
    write_ok = bool(writer.Write(str(iges)))
    reader = IGESControl_Reader()
    read_status = reader.ReadFile(str(iges))
    reader.TransferRoots()
    iges_shape = reader.OneShape()
    payload = {
        "format": "SM35_CAD_MATRIX_V1", "step_valid": bool(BRepCheck_Analyzer(step_shape.wrapped).IsValid()),
        "iges_write": write_ok, "iges_read_status": int(read_status),
        "iges_valid": bool(BRepCheck_Analyzer(iges_shape).IsValid()), "iges_done_constant": int(IFSelect_RetDone),
    }
    write_json(args.output, payload)
    return 0 if payload["step_valid"] and write_ok and payload["iges_valid"] and read_status == IFSelect_RetDone else 2


if __name__ == "__main__":
    raise SystemExit(main())
