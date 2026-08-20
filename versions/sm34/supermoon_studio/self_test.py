from __future__ import annotations
import json
import tempfile
from pathlib import Path
from .analysis_engine import analyzer
from .report_engine import build_scientific_pdf, build_patent_pdf
from .sm32_bridge import runtime_status as sm32_runtime_status
from .sm34_bridge import runtime_status as sm34_runtime_status, validation as sm34_validation

SAMPLE="""# Example Research Master Prompt
Objective: design and analyze a reproducible scientific workflow for a turbulent CFD study.
Use governing equations, explicit boundary conditions, dimensional analysis, uncertainty quantification and independent verification.
Require mesh convergence, GCI, Richardson extrapolation, benchmark validation, residual checks, provenance hashes, versioned environment and evidence-backed claims.
Deliver a scientific PDF and patent-style technical specification. Do not claim certification without qualified external evidence.
"""

def main():
    a=analyzer.analyze(SAMPLE,2)
    assert a["analysis_id"] and a["risk"]["risk_class"]
    assert a["new_universe"]["selected_tracks"]
    assert sm34_runtime_status()["available"]
    assert sm34_validation()["status"] == "PASS"
    with tempfile.TemporaryDirectory() as td:
        p1=build_scientific_pdf(SAMPLE,a,Path(td)/"scientific.pdf")
        p2=build_patent_pdf(SAMPLE,a,Path(td)/"patent.pdf")
        for p in (p1,p2):
            assert p.exists() and p.read_bytes().startswith(b"%PDF") and p.stat().st_size>2000
    print(json.dumps({"ok":True,"sm34_runtime":sm34_runtime_status(),"sm32_runtime":sm32_runtime_status(),"analysis_id":a["analysis_id"],"scientific_readiness":a["scientific_readiness_score"]},indent=2))

if __name__=="__main__":main()
