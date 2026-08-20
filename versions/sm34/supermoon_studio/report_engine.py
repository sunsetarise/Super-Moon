from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import hashlib
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from .config import settings

NAVY = colors.HexColor("#102A43")
BLUE = colors.HexColor("#1261A0")
LIGHT = colors.HexColor("#EAF2F8")
INK = colors.HexColor("#101820")
MUTED = colors.HexColor("#51606D")


def _safe(x):
    return escape(str(x)).replace("\n", "<br/>")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=NAVY, alignment=TA_LEFT, spaceAfter=10),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14, textColor=MUTED, spaceAfter=12),
        "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=NAVY, spaceBefore=10, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=BLUE, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.2, textColor=INK, spaceAfter=5),
        "small": ParagraphStyle("small", parent=ss["BodyText"], fontName="Helvetica", fontSize=7.8, leading=10.8, textColor=MUTED, spaceAfter=4),
        "callout": ParagraphStyle("callout", parent=ss["BodyText"], fontName="Helvetica-Bold", fontSize=9.2, leading=13.2, textColor=NAVY, backColor=LIGHT, borderPadding=7, spaceBefore=5, spaceAfter=7),
    }


def _header_footer(canvas, doc, title):
    canvas.saveState()
    w,h=A4
    canvas.setFillColor(NAVY); canvas.rect(0,h-11*mm,w,11*mm,fill=1,stroke=0)
    canvas.setFillColor(colors.white); canvas.setFont("Helvetica-Bold",7.5); canvas.drawString(16*mm,h-7*mm,"SUPER MOON 34 NEW UNIVERSE PROMPT STUDIO")
    canvas.setFillColor(MUTED); canvas.setFont("Helvetica",7); canvas.drawString(16*mm,8*mm,title[:90])
    canvas.drawRightString(w-16*mm,8*mm,f"Page {doc.page}")
    canvas.restoreState()


def _table(data, widths=None, header=True):
    t=Table(data,colWidths=widths,repeatRows=1 if header else 0,hAlign="LEFT")
    style=[("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#C7D3DD")),("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),7.8),("LEADING",(0,0),(-1,-1),10)]
    if header:
        style += [("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold")]
    for r in range(1 if header else 0,len(data)):
        if r%2==0: style.append(("BACKGROUND",(0,r),(-1,r),colors.HexColor("#F6F9FB")))
    t.setStyle(TableStyle(style)); return t


def _bullet(story, items, st, limit=20):
    for item in items[:limit]:
        story.append(Paragraph("• "+_safe(item), st["body"]))


def _cover(story, title, subtitle, analysis, st):
    story += [Spacer(1,18*mm), Paragraph(title,st["title"]), Paragraph(subtitle,st["subtitle"]), Spacer(1,6*mm)]
    risk=analysis["risk"]
    data=[
        ["Analysis ID",analysis["analysis_id"],"Prompt SHA-256",analysis["prompt_hash_sha256"][:24]+"…"],
        ["Scientific readiness",f"{analysis['scientific_readiness_score']}/100","Architecture score",f"{analysis['overall_architecture_score']}/100"],
        ["Risk class",risk["risk_class"],"CRI",f"{risk['cri']:.3f}"],
        ["SM34 runtime", "ACTIVE" if analysis.get("runtime",{}).get("available") else "FALLBACK", "Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
    ]
    story.append(_table([[Paragraph(_safe(c),st["small"]) for c in row] for row in data], [35*mm,55*mm,35*mm,55*mm], header=False))
    story += [Spacer(1,8*mm),Paragraph("Evidence discipline",st["h2"]),Paragraph("This document distinguishes prompt-derived analysis from externally validated scientific results. No external solver, laboratory, patent novelty search, certification authority, or third-party qualification is represented as having been executed unless separately evidenced.",st["callout"])]


def build_scientific_pdf(prompt: str, analysis: dict, output_path: Path) -> Path:
    st=_styles(); output_path.parent.mkdir(parents=True,exist_ok=True)
    title="Scientific Analysis & Research Architecture Report"
    doc=SimpleDocTemplate(str(output_path),pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=18*mm,bottomMargin=16*mm,title=title,author="SuperMoon Prompt Studio")
    story=[]; _cover(story,title,analysis["title"],analysis,st)
    story += [PageBreak(),Paragraph("1. Executive Scientific Assessment",st["h1"]),Paragraph(_safe(analysis["result_synthesis"]["interpretation"]),st["body"])]
    score_rows=[["Dimension","Score / 100"]]+[[k.replace("_"," ").title(),f"{v:.1f}"] for k,v in analysis["coverage_scores"].items()]
    story.append(_table(score_rows,[110*mm,40*mm]))
    story += [Paragraph("Primary strengths",st["h2"])]
    _bullet(story,[f"{x['area'].replace('_',' ').title()}: {x['score']}/100" for x in analysis["strengths"]],st)
    story += [Paragraph("Primary gaps",st["h2"])]
    _bullet(story,[f"{x['area'].replace('_',' ').title()}: {x['score']}/100" for x in analysis["gaps"]],st)

    story += [Paragraph("2. Problem Formalization",st["h1"]),Paragraph("Detected objectives",st["h2"])]
    _bullet(story,analysis["formalization"]["goals"],st)
    story.append(Paragraph("Constraints and mandatory conditions",st["h2"])); _bullet(story,analysis["formalization"]["constraints"],st)
    story.append(Paragraph("Requested outputs",st["h2"])); _bullet(story,analysis["formalization"]["requested_outputs"],st)
    if analysis["formalization"]["equation_candidates"]:
        story.append(Paragraph("Equation-like statements",st["h2"])); _bullet(story,analysis["formalization"]["equation_candidates"],st,12)

    story += [Paragraph("3. Domain & Computational Regime",st["h1"])]
    drows=[["Detected domain","Lexical hits","Confidence"]]+[[d["domain"],str(d["hits"]),f"{d['confidence']:.2f}"] for d in analysis["domains"]]
    if len(drows)==1:drows.append(["General / cross-domain","0","0.35"])
    story.append(_table(drows,[95*mm,35*mm,30*mm]))

    story += [Paragraph("4. Super Moon 34 New Universe Capability Routing",st["h1"])]
    universe=analysis.get("new_universe",{})
    tracks=universe.get("selected_tracks",[])
    track_rows=[["Track","Capability","Backend","Available","Gates"]]+[
        [x.get("track_id",""),x.get("name",""),x.get("backend",""),str(x.get("backend_available",False)),", ".join(x.get("gates",[]))]
        for x in tracks
    ]
    if len(track_rows)==1: track_rows.append(["—","No route selected","—","False","—"])
    story.append(_table(track_rows,[15*mm,66*mm,28*mm,22*mm,28*mm]))
    story.append(Paragraph(_safe(universe.get("truth_boundary","")),st["callout"]))

    story += [Paragraph("5. Computational Risk & Escalation",st["h1"])]
    r=analysis["risk"]
    rr=[["Metric","Assessment"],["CRI",f"{r['cri']:.4f}"],["Risk class",r["risk_class"]],["Scale class",r["scale_class"]],["External qualified tool mandatory",str(r["mandatory_external_tool"])],["Independent verification required",str(r["required_independent_verification"])],["Human review required",str(r["required_human_review"])],["Engine",r["engine"]]]
    story.append(_table(rr,[75*mm,90*mm]))
    if r["mandatory_reasons"]: _bullet(story,["Mandatory trigger: "+x for x in r["mandatory_reasons"]],st)

    story += [Paragraph("6. Verification, Validation and UQ Architecture",st["h1"])]
    story.append(Paragraph("Recommended interpretation",st["body"])); _bullet(story,[
        "Verification answers whether the equations and algorithms are solved correctly; validation addresses whether the model is adequate for the intended reality or benchmark.",
        "High-risk conclusions should not rely on a single computational path. Use internal SM34 computation as research/cross-check support and close the selected New Universe gates with real evidence when qualification policy requires it.",
        "Treat discretization error, parameter uncertainty, model-form uncertainty and data uncertainty as separate budget components.",
        "Document non-convergence and disagreement as results rather than silently filtering them out.",
    ],st)

    story += [Paragraph("7. Research Orchestration DAG",st["h1"])]
    wrows=[["Stage","Name","Purpose"]]+[[x["id"],x["name"],Paragraph(_safe(x["description"]),st["small"])] for x in analysis["workflow"]]
    story.append(_table(wrows,[13*mm,42*mm,110*mm]))

    story += [Paragraph("8. Claims & Evidence Audit",st["h1"])]
    claims=analysis["claims_requiring_evidence"]
    if claims:
        for i,c in enumerate(claims[:12],1):
            story.append(Paragraph(f"Claim {i}: {_safe(c['claim'])}",st["body"])); story.append(Paragraph(_safe(c["recommended_action"]),st["small"]))
    else: story.append(Paragraph("No high-strength claim patterns were detected by the deterministic claim scanner.",st["body"]))

    story += [Paragraph("9. Knowledge Alignment",st["h1"]),Paragraph("The following excerpts were retrieved from the integrated Super Moon 34 New Universe knowledge corpus based on the prompt's dominant domains and governance requirements.",st["body"])]
    for i,h in enumerate(analysis["knowledge_hits"][:8],1):
        story.append(Paragraph(f"Knowledge hit {i} — lines {h.get('start_line')}–{h.get('end_line')} — {_safe(h.get('heading',''))}",st["h2"]))
        story.append(Paragraph(_safe(h.get("excerpt","")[:2600]),st["small"]))

    story += [Paragraph("10. Recommendations",st["h1"])]
    _bullet(story,analysis["recommendations"] or ["No major structural recommendation generated."],st)

    story += [Paragraph("11. Reproducibility Record",st["h1"])]
    rec=[["Artifact","Value"],["Prompt SHA-256",analysis["prompt_hash_sha256"]],["Analysis ID",analysis["analysis_id"]],["Knowledge query",analysis.get("knowledge_query","")],["Runtime source",analysis.get("runtime",{}).get("source","")],["External validation","NOT EXECUTED BY THIS REPORT GENERATOR"]]
    story.append(_table(rec,[55*mm,110*mm]))

    story += [Paragraph("Appendix A — Master Prompt Excerpt",st["h1"]),Paragraph(_safe(prompt[:18000]),st["small"])]
    doc.build(story,onFirstPage=lambda c,d:_header_footer(c,d,title),onLaterPages=lambda c,d:_header_footer(c,d,title))
    return output_path


def build_patent_pdf(prompt: str, analysis: dict, output_path: Path) -> Path:
    st=_styles(); output_path.parent.mkdir(parents=True,exist_ok=True)
    title="Patent-Style Technical Specification"
    doc=SimpleDocTemplate(str(output_path),pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=18*mm,bottomMargin=16*mm,title=title,author="SuperMoon Prompt Studio")
    story=[]; _cover(story,title,"SuperMoon Prompt Analysis, Research Automation, Verification & PDF Generation Interface",analysis,st)
    story += [PageBreak(),Paragraph("Notice",st["h1"]),Paragraph("This is a patent-style technical drafting artifact, not a legal opinion, filing recommendation, novelty determination, freedom-to-operate analysis, or representation of patentability. A professional prior-art search and jurisdiction-specific counsel remain necessary before filing.",st["callout"])]
    sections = [
        ("1. Technical Field","The disclosure relates to computer-implemented scientific research orchestration, prompt analysis, numerical-governance workflows, knowledge retrieval, evidence management, interactive three-dimensional research interfaces, and automated generation of scientific and patent-style PDF artifacts."),
        ("2. Background","Complex master prompts often combine objectives, mathematical methods, software requirements, risk-sensitive decision logic and reporting requirements in unstructured text. A technical challenge is converting that text into a traceable computational workflow while preventing unsupported claims from being treated as validated results."),
        ("3. Summary of the System","The disclosed system ingests a master prompt, computes a structural and governance analysis, queries the compressed Super Moon 34 New Universe corpus, invokes embedded qualified research and New Universe capability registries, visualizes the workflow through a Babylon.js 9 interface, and produces evidence-disciplined scientific and patent-style reports."),
        ("4. System Architecture","A backend service provides prompt ingestion, knowledge retrieval, runtime bridging, computational risk assessment, analysis synthesis and PDF generation. A browser front end renders control panels and a three-dimensional research graph. A seekable compressed knowledge cache preserves the full canonical corpus while enabling chunk-level retrieval."),
        ("5. Knowledge Integration","The canonical SuperMoon corpus remains preserved as a compressed text artifact. During setup, a chunk store and compact SQLite conceptual-term metadata index are generated. Conceptual terms are indexed; exact identifier queries can fall back to canonical streaming search, reducing index inflation from large enumerated catalogs."),
        ("6. Analysis Pipeline","The analyzer detects domains, sections, goals, constraints, outputs, equation-like statements, risk triggers, evidence-strength claims, verification/validation/UQ coverage, reproducibility controls and reporting requirements. The output is represented as structured machine-readable data and a staged research workflow."),
        ("7. Risk-Aware Execution Governance","The system computes a Computational Risk Index through the embedded qualified runtime when available. The outcome determines whether external qualified tools, independent verification and human review are mandatory, recommended or optional."),
        ("8. Evidence and Claim Governance","High-strength assertions are separated from demonstrated results. Claims indicating certification, proof, guaranteed performance, absolute success or production readiness are flagged for evidence attachment or wording downgrade."),
        ("9. Three-Dimensional Interface","Babylon.js 9 renders an interactive research nucleus and workflow nodes representing formalization, model selection, risk, routing, verification, UQ, evidence and reporting. Visual state can be updated from backend analysis without assigning scientific truth to visualization alone."),
        ("10. PDF Artifact Generation","The system generates a scientific report and patent-style technical specification directly from the structured analysis. Each artifact carries prompt hashes, analysis identifiers, risk state, limitations and a statement distinguishing prompt analysis from external validation."),
    ]
    for h,b in sections:
        story.append(Paragraph(h,st["h1"])); story.append(Paragraph(b,st["body"]))

    story += [Paragraph("11. Example Processing Sequence",st["h1"])]
    _bullet(story,[f"{x['id']} — {x['name']}: {x['description']}" for x in analysis["workflow"]],st,20)

    story += [Paragraph("12. Illustrative Claims",st["h1"]),Paragraph("The following claims are drafting examples generated from the implemented architecture and should be reviewed against prior art and jurisdiction-specific requirements.",st["body"])]
    claims=[
        "1. A computer-implemented system comprising: a prompt ingestion module configured to receive a scientific or engineering master prompt; a deterministic analysis engine configured to extract objectives, constraints, computational domains, evidence-sensitive claims and research-governance requirements; a knowledge retrieval engine configured to retrieve relevant chunks from a compressed indexed corpus; a risk engine configured to determine a computational risk state; and a report engine configured to generate a scientific PDF artifact from a structured analysis record.",
        "2. The system of claim 1, wherein the knowledge retrieval engine stores chunk payloads in independently compressed blocks and stores chunk metadata and compact searchable conceptual-term summaries in a relational index.",
        "3. The system of claim 1, wherein the risk engine invokes an embedded qualified research runtime and a Super Moon 34 capability router and returns at least a computational risk index, a risk class, selected P01-P11 or A01-A05 tracks, external-tool availability, gate states, an independent-verification requirement and a human-review requirement.",
        "4. The system of claim 1, further comprising a three-dimensional browser visualization engine implemented with Babylon.js 9 and configured to visualize research workflow stages as interactive nodes whose state is updated from the structured analysis record.",
        "5. The system of claim 1, wherein the deterministic analysis engine flags high-strength claims lacking referenced benchmark, validation, qualification, experimental or external-reproduction evidence.",
        "6. The system of claim 1, wherein generation of a patent-style PDF and generation of a scientific PDF use the same prompt hash and analysis identifier to maintain traceability between source prompt and output artifacts.",
        "7. The system of claim 1, wherein a fallback exact-search path scans the canonical compressed corpus for identifier-heavy queries excluded from the compact conceptual index.",
        "8. A computer-implemented method comprising receiving a master prompt; normalizing the prompt; computing research-governance coverage; assessing computational risk; retrieving relevant knowledge chunks; creating an evidence-aware workflow; and generating at least one portable document format artifact carrying a cryptographic identifier of the received prompt.",
        "9. The method of claim 8, further comprising preventing an externally unvalidated computational conclusion from being labeled as certified, experimentally validated, independently reproduced or qualification-acceptable solely by reason of generation by the system.",
        "10. A non-transitory computer-readable medium storing instructions that, when executed, cause a computing device to perform the method of claim 8.",
    ]
    for c in claims: story.append(Paragraph(c,st["body"]))

    story += [Paragraph("13. Prompt-Derived Embodiment Profile",st["h1"])]
    rows=[["Property","Observed / inferred value"],["Analysis ID",analysis["analysis_id"]],["Scientific readiness",str(analysis["scientific_readiness_score"])],["Patent drafting readiness",str(analysis["patent_drafting_readiness_score"])],["Risk class",analysis["risk"]["risk_class"]],["Detected domains",", ".join(d["domain"] for d in analysis["domains"][:5]) or "General"],["Claims requiring evidence",str(len(analysis["claims_requiring_evidence"]))]]
    story.append(_table(rows,[62*mm,103*mm]))

    story += [Paragraph("14. Known Limitations",st["h1"])]
    _bullet(story,[
        "The analyzer is deterministic and lexical/structural; it does not by itself establish scientific truth or patent novelty.",
        "The included external-tool registry does not imply certification of third-party solvers or hardware.",
        "Full-corpus knowledge integration improves retrieval and traceability but does not transform inherited text into verified evidence.",
        "Patent claims may require substantial narrowing, redrafting and prior-art differentiation before filing.",
        "Safety-critical or certification-sensitive decisions require the escalation paths identified by the risk engine.",
    ],st)
    story += [Paragraph("Appendix A — Source Master Prompt Excerpt",st["h1"]),Paragraph(_safe(prompt[:16000]),st["small"])]
    doc.build(story,onFirstPage=lambda c,d:_header_footer(c,d,title),onLaterPages=lambda c,d:_header_footer(c,d,title))
    return output_path


def output_name(kind: str, analysis: dict) -> Path:
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    slug=re.sub(r"[^A-Za-z0-9_-]+","_",analysis.get("title","prompt"))[:50].strip("_") or "prompt"
    return settings.output_dir / f"SM34_NEW_UNIVERSE_{kind.upper()}_{slug}_{stamp}.pdf"
