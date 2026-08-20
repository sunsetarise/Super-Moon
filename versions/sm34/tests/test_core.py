from pathlib import Path
from supermoon_studio.analysis_engine import analyzer
from supermoon_studio.report_engine import build_scientific_pdf, build_patent_pdf

def test_analysis_and_reports(tmp_path:Path):
    p="Objective: analyze a CFD model with governing equations, validation benchmark, verification, uncertainty, provenance and scientific PDF. Require airworthiness review."
    a=analyzer.analyze(p,0)
    assert a["scientific_readiness_score"]>=0
    assert a["risk"]["mandatory_external_tool"] is True
    assert a["runtime"]["available"] is True
    assert any(track["track_id"].startswith("A") for track in a["new_universe"]["selected_tracks"])
    s=build_scientific_pdf(p,a,tmp_path/"s.pdf"); t=build_patent_pdf(p,a,tmp_path/"p.pdf")
    assert s.read_bytes()[:4]==b"%PDF" and t.read_bytes()[:4]==b"%PDF"
