"""Environment-aware policy for inherited optional CAD integration tests.

The SM34 adapter contract reports CadQuery/OCCT as UNAVAILABLE when its real
backend is absent. The inherited SM31 CAD tests predate that contract and
instantiate CadKernel unconditionally. They are skipped only when the actual
CadQuery module is unavailable; no mock geometry or fallback result is used.
"""

from __future__ import annotations

import importlib.util

import pytest


CADQUERY_TESTS = {
    "test_cad_primitives_and_boolean",
    "test_step_roundtrip",
    "test_iges_roundtrip",
    "test_heal_audit",
    "test_parametric_dag",
    "test_aircraft_cad",
    "test_cad_geometry_parametric_assembly_and_io",
    "test_aircraft_full",
}


def pytest_collection_modifyitems(items):
    if importlib.util.find_spec("cadquery") is not None:
        return
    marker = pytest.mark.skip(reason="real CadQuery/OCCT backend is unavailable; SM34 reports this backend as UNAVAILABLE")
    for item in items:
        if item.name in CADQUERY_TESTS:
            item.add_marker(marker)
