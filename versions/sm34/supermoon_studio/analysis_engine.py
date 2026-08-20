from __future__ import annotations
import hashlib
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Iterable
from .knowledge import index
from .sm32_bridge import assess, runtime_status as sm32_runtime_status
from .sm34_bridge import align_prompt, runtime_status as sm34_runtime_status

SECTION_RE = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*[.)]?\s+|[A-Z][.)]\s+)(.+)$", re.M)
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9_+./:-]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")

DOMAIN_TERMS = {
    "CFD / Fluids": ["cfd","fluid","navier","stokes","aerodynamic","turbulence","mach","reynolds","shock","compressible"],
    "Structures / FEA": ["fea","finite element","structural","stress","strain","buckling","fatigue","material","contact"],
    "Aerospace": ["aircraft","aerospace","airworthiness","flight","wing","propulsion","hypersonic","orbital"],
    "Optimization": ["optimization","optimizer","design space","multi-objective","objective function","constraint","pareto"],
    "Statistics / UQ": ["uncertainty","monte carlo","bayesian","sensitivity","reliability","confidence","probability","uq"],
    "ML / AI": ["machine learning","neural","transformer","reinforcement","diffusion","training","gpu","model"],
    "HPC / Numerics": ["hpc","mpi","petsc","distributed","sparse","solver","numerical","conditioning","precision","scaling","slurm"],
    "Scientific Research": ["hypothesis","experiment","scientific","validation","verification","reproducibility","evidence"],
    "Software / Systems": ["api","backend","frontend","python","javascript","database","orchestration","workflow","runtime"],
    "Security Research": ["security","threat","vulnerability","forensic","osint","cyber","attack surface"],
}

COVERAGE = {
    "problem_formalization": ["objective","problem","input","output","constraint","assumption","boundary condition","initial condition","governing"],
    "mathematical_rigor": ["equation","model","dimension","nondimensional","stability","convergence","condition","residual","error"],
    "verification": ["verification","independent","cross-check","manufactured solution","gci","richardson","residual","regression"],
    "validation": ["validation","experimental","benchmark","reference data","acceptance criteria","ground truth"],
    "uncertainty": ["uncertainty","uq","monte carlo","sensitivity","bayesian","confidence interval","reliability","distribution"],
    "reproducibility": ["reproducibility","seed","manifest","environment","version","hash","provenance","deterministic"],
    "evidence": ["evidence","claim","audit","traceability","source","limitation","failure mode","known defect"],
    "orchestration": ["workflow","dag","orchestration","checkpoint","retry","fault","automation","scheduler","pipeline"],
    "risk_governance": ["risk","criticality","safety","qualification","human review","certification","escalation","cri"],
    "reporting": ["report","pdf","scientific","patent","executive summary","machine-readable","result"],
}

TRIGGERS = {
    "human_safety": ["human safety","person safety","injury","fatal"],
    "life_critical": ["life critical","life-critical"],
    "regulatory_certification": ["regulatory certification","certification"],
    "airworthiness": ["airworthiness"],
    "nuclear_safety": ["nuclear safety"],
    "critical_infrastructure": ["critical infrastructure"],
    "medical_device_regulatory": ["medical device","medical-device"],
    "flight_critical_structure": ["flight critical","flight-critical"],
    "extreme_nonlinear_structure": ["extreme nonlinear","large deformation contact"],
    "very_large_production_cfd": ["billion-cell","billion cell","production cfd"],
    "extreme_sparse_distributed": ["extreme sparse","distributed sparse"],
    "industrial_cad_interoperability": ["industrial cad","cad interoperability"],
    "production_gpu_beyond_validation": ["production gpu","large gpu training"],
    "formal_legal_acceptance": ["legal acceptance","contractual acceptance"],
    "independent_authority_review": ["independent authority","authority review"],
}

CLAIM_PATTERNS = [
    re.compile(r"\b(?:guarantee|guaranteed|prove|proven|certified|replace every|beat|best in the world|100%|zero error|always|never fails)\b", re.I),
    re.compile(r"\b(?:fully implemented|production[- ]ready|certification[- ]acceptable|industrial parity)\b", re.I),
]


def _present(text: str, terms: Iterable[str]) -> int:
    low = text.lower()
    return sum(1 for term in terms if term in low)


def _coverage_score(text: str, terms: list[str]) -> float:
    hits = _present(text, terms)
    return round(min(100.0, 100.0 * hits / max(4, min(len(terms), 7))), 1)


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        s = line.strip().lstrip("#").strip()
        if len(s) >= 6:
            return s[:140]
    return "Untitled Master Prompt"


def _first_sentences(text: str, keywords: list[str], limit: int = 5) -> list[str]:
    out = []
    for s in SENTENCE_RE.split(text):
        c = " ".join(s.split())
        low = c.lower()
        if 20 <= len(c) <= 420 and any(k in low for k in keywords):
            out.append(c)
            if len(out) >= limit: break
    return out


def _claims(text: str, limit: int = 16) -> list[dict]:
    out = []
    for sentence in SENTENCE_RE.split(text):
        s = " ".join(sentence.split())
        if not s: continue
        if any(p.search(s) for p in CLAIM_PATTERNS):
            out.append({"claim": s[:500], "status": "REQUIRES_EVIDENCE", "recommended_action": "Attach benchmark, test, qualification, external reproduction, or downgrade claim wording."})
            if len(out) >= limit: break
    return out


def _domain_scores(text: str) -> list[dict]:
    low = text.lower()
    rows = []
    for domain, terms in DOMAIN_TERMS.items():
        hits = sum(low.count(t) for t in terms)
        if hits:
            rows.append({"domain": domain, "hits": hits, "confidence": round(min(0.98, 0.35 + math.log1p(hits)/5), 3)})
    return sorted(rows, key=lambda x: x["hits"], reverse=True)[:8]


def _infer_problem_units(text: str) -> tuple[float, bool]:
    low = text.lower(); distributed = any(x in low for x in ("distributed","mpi","multi-node","cluster","billion-cell","billion cell"))
    scale = 1000.0
    patterns = [(r"(\d+(?:\.\d+)?)\s*billion", 1e9), (r"(\d+(?:\.\d+)?)\s*million", 1e6), (r"(\d+(?:\.\d+)?)\s*trillion", 1e12)]
    for pat, mult in patterns:
        m = re.search(pat, low)
        if m:
            scale = max(scale, float(m.group(1))*mult)
    if "extreme scale" in low or "extreme-scale" in low: scale=max(scale,1e9)
    return scale, distributed


def _risk_profile(text: str, scores: dict[str, float], domains: list[dict]) -> tuple[dict, set[str], float, bool]:
    low = text.lower()
    triggers = {name for name, terms in TRIGGERS.items() if any(t in low for t in terms)}
    problem_units, distributed = _infer_problem_units(text)
    profile = {
        "criticality": min(1.0, .18 + .12*len(triggers) + (.22 if any("Aerospace" in d["domain"] for d in domains) else 0)),
        "scale": min(1.0, math.log10(max(problem_units,1))/10 + (.15 if distributed else 0)),
        "uncertainty": max(.05, 1 - scores["uncertainty"]/120),
        "impact": min(1.0, .25 + .12*len(triggers)),
        "evidence_deficiency": max(.05, 1 - scores["evidence"]/110),
        "novelty": .72 if any(x in low for x in ("novel","new","next generation","future","unprecedented","mastermind")) else .35,
        "qualification_deficiency": .72 if not any(x in low for x in ("qualified tool","qualification evidence","q4","q5")) else .35,
    }
    return profile, triggers, problem_units, distributed


def _workflow(risk: dict) -> list[dict]:
    stages = [
        ("01","Ingest & normalize","Hash prompt, identify sections, constraints, claims and domain vocabulary."),
        ("02","Problem formalization","Define objective, inputs, outputs, governing equations, assumptions, boundary/initial conditions and acceptance criteria."),
        ("03","Dimensional & regime analysis","Check units, nondimensional groups, model validity and operating regime."),
        ("04","Risk / scale assessment",f"Compute CRI and escalation policy. Current inferred class: {risk['risk_class']} (CRI={risk['cri']:.3f})."),
        ("05","SM34 capability routing","Select New Universe P01-P11 / A01-A05 tracks and expose unavailable physical backends."),
        ("06","Execution plan","Build reproducible DAG, parameter sweeps, seeds, manifests, checkpoints and failure semantics."),
        ("07","Independent verification","Require a second numerical/analytical path when risk policy indicates it."),
        ("08","Validation","Compare against benchmark, experimental, reference, or acceptance data."),
        ("09","UQ & sensitivity","Quantify numerical/parameter/model uncertainty and sensitivity."),
        ("10","Discrepancy analysis","Classify solver disagreement and investigate mesh, model, tolerance, implementation and data causes."),
        ("11","Evidence & provenance","Hash artifacts, track source lineage, limitations, known defects and claim level."),
        ("12","Decision synthesis","Separate observed result, inference, hypothesis, limitation and recommendation."),
        ("13","Scientific / patent PDF","Generate evidence-backed scientific report and patent-style technical specification."),
    ]
    return [{"id":a,"name":b,"description":c} for a,b,c in stages]


def _recommendations(scores: dict[str,float], claims: list[dict], risk: dict) -> list[str]:
    rec=[]
    labels={
        "problem_formalization":"Add explicit problem variables, governing equations, boundary/initial conditions and acceptance criteria.",
        "verification":"Add an independent verification route, residual checks, order/GCI or manufactured-solution tests where applicable.",
        "validation":"Add benchmark or experimental validation targets and pass/fail tolerances.",
        "uncertainty":"Define uncertain parameters, distributions, sensitivity method and numerical/model uncertainty budget.",
        "reproducibility":"Pin versions, seeds, manifests, hashes and clean-environment replay instructions.",
        "evidence":"Map every strong claim to a specific test, benchmark, source, artifact or qualification record.",
    }
    for k,msg in labels.items():
        if scores[k] < 65: rec.append(msg)
    if claims: rec.append(f"Downgrade or evidence {len(claims)} high-strength claim(s) before treating the prompt as a scientific conclusion.")
    if risk.get("mandatory_external_tool"): rec.append("SM34 New Universe escalation is active: internal output remains research/support output until the required qualified external path and evidence are supplied.")
    if risk.get("required_human_review"): rec.append("Add a named human review gate and decision authority before final acceptance.")
    return rec[:12]


class PromptAnalyzer:
    def analyze(self, text: str, knowledge_limit: int = 8) -> dict:
        prompt = (text or "").strip()
        if len(prompt) < 20:
            raise ValueError("Master prompt is too short; provide at least 20 characters.")
        words = WORD_RE.findall(prompt); lines = prompt.splitlines(); sections = [m.group(1).strip()[:180] for m in SECTION_RE.finditer(prompt)]
        scores = {k:_coverage_score(prompt,v) for k,v in COVERAGE.items()}
        domains = _domain_scores(prompt)
        claims = _claims(prompt)
        profile,triggers,problem_units,distributed = _risk_profile(prompt,scores,domains)
        risk = assess(profile,triggers,problem_units,distributed)
        new_universe = align_prompt(prompt)
        query_terms = []
        for d in domains[:3]: query_terms += DOMAIN_TERMS[d["domain"]][:2]
        query_terms += ["verification","uncertainty","evidence","orchestration"]
        seen=[]
        for x in query_terms:
            if x not in seen: seen.append(x)
        knowledge_query = " ".join(seen[:6])
        knowledge_hits = index.search(knowledge_query, knowledge_limit) if knowledge_query else []
        avg = statistics.fmean(scores.values())
        scientific_readiness = round(.55*avg + .15*scores["verification"] + .10*scores["validation"] + .10*scores["uncertainty"] + .10*scores["evidence"],1)
        patent_readiness = round(.40*avg + .20*scores["problem_formalization"] + .15*scores["evidence"] + .15*scores["reporting"] + .10*max(0,100-len(claims)*5),1)
        goals = _first_sentences(prompt,["objective","goal","mission","create","build","design","develop","analyze","generate"],6)
        constraints = _first_sentences(prompt,["must","shall","do not","without","constraint","limit","required","mandatory"],8)
        outputs = _first_sentences(prompt,["output","deliver","report","pdf","result","file","dataset","patent","scientific"],8)
        eq_lines=[ln.strip()[:260] for ln in lines if "=" in ln and any(x in ln.lower() for x in ("cri","error","risk","score","loss","objective","sum","delta","sigma","mu","p(","f("))][:20]
        strong = sorted(scores.items(), key=lambda x:x[1], reverse=True)[:4]
        weak = sorted(scores.items(), key=lambda x:x[1])[:4]
        recommendations = _recommendations(scores,claims,risk)
        return {
            "analysis_id": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            "title": _extract_title(prompt),
            "prompt_hash_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "metrics": {
                "characters": len(prompt), "words": len(words), "lines": len(lines), "sections_detected": len(sections),
                "equation_like_lines": len(eq_lines), "strong_claims": len(claims), "knowledge_hits": len(knowledge_hits),
                "sm34_tracks_selected": len(new_universe["selected_tracks"]),
                "sm34_gates_selected": len(new_universe["required_gates"]),
            },
            "domains": domains,
            "coverage_scores": scores,
            "overall_architecture_score": round(avg,1),
            "scientific_readiness_score": scientific_readiness,
            "patent_drafting_readiness_score": patent_readiness,
            "risk": risk,
            "risk_input_profile": profile,
            "formalization": {
                "goals": goals or ["No explicit objective sentence detected."],
                "constraints": constraints or ["No explicit constraint sentence detected."],
                "requested_outputs": outputs or ["No explicit output sentence detected."],
                "equation_candidates": eq_lines,
                "section_outline": sections[:80],
            },
            "claims_requiring_evidence": claims,
            "strengths": [{"area":k,"score":v} for k,v in strong],
            "gaps": [{"area":k,"score":v} for k,v in weak],
            "workflow": _workflow(risk),
            "new_universe": new_universe,
            "recommendations": recommendations,
            "knowledge_query": knowledge_query,
            "knowledge_hits": knowledge_hits,
            "result_synthesis": {
                "status": "ANALYSIS_COMPLETE_NOT_EXTERNAL_VALIDATION",
                "interpretation": "The engine has analyzed prompt structure, scientific governance, risk, reproducibility, verification/validation coverage, UQ, evidence posture and Super Moon 34 New Universe track alignment. It has not fabricated external solver, hardware, endurance, laboratory, certification, novelty-search or independent-reproduction results.",
                "next_executable_actions": recommendations[:6],
            },
            "runtime": sm34_runtime_status(),
            "legacy_sm32_runtime": sm32_runtime_status(),
        }

analyzer = PromptAnalyzer()
