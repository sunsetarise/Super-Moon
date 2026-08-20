from __future__ import annotations
import sys
from pathlib import Path
from .config import settings

SRC = settings.sm32_runtime_dir / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

RUNTIME_AVAILABLE = False
IMPORT_ERROR = None
try:
    import supermoon32  # noqa: F401
    from supermoon32.qualified.risk import RiskProfile, assess_risk, classify_scale, decision_matrix
    from supermoon32.qualified.enums import ScaleClass, RiskClass, ConfidenceClass
    from supermoon32.qualified.verification import confidence_score
    RUNTIME_AVAILABLE = True
except Exception as exc:  # pragma: no cover - diagnostics path
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def runtime_status() -> dict:
    return {
        "available": RUNTIME_AVAILABLE,
        "source": str(SRC),
        "error": IMPORT_ERROR,
    }


def assess(profile: dict, triggers: set[str], problem_units: float = 1000.0, distributed: bool = False) -> dict:
    """Use the actual embedded SM32Q risk engine when available, with a compatible fallback."""
    if RUNTIME_AVAILABLE:
        rp = RiskProfile(
            criticality=float(profile.get("criticality", 0)),
            scale=float(profile.get("scale", 0)),
            uncertainty=float(profile.get("uncertainty", 0)),
            impact=float(profile.get("impact", 0)),
            evidence_deficiency=float(profile.get("evidence_deficiency", 0)),
            novelty=float(profile.get("novelty", 0)),
            qualification_deficiency=float(profile.get("qualification_deficiency", 0)),
            triggers=frozenset(triggers),
        )
        ra = assess_risk(rp)
        sc = classify_scale(problem_units, distributed=distributed, billion_scale=problem_units >= 1e9)
        dm = decision_matrix(ra.risk_class, sc)
        return {
            "cri": ra.cri,
            "risk_class": ra.risk_class.value,
            "mandatory_external_tool": ra.mandatory_external_tool,
            "mandatory_reasons": list(ra.mandatory_reasons),
            "required_independent_verification": ra.required_independent_verification,
            "required_human_review": ra.required_human_review,
            "scale_class": sc.name,
            "decision_matrix": dm,
            "engine": "embedded-supermoon32.qualified",
        }

    weights = {
        "criticality": .20, "scale": .12, "uncertainty": .12, "impact": .20,
        "evidence_deficiency": .12, "novelty": .08, "qualification_deficiency": .16,
    }
    cri = sum(weights[k] * float(profile.get(k, 0)) for k in weights)
    cls = "LOW" if cri < .2 else "MODERATE" if cri < .4 else "HIGH" if cri < .6 else "VERY_HIGH" if cri < .8 else "CRITICAL"
    return {
        "cri": cri, "risk_class": cls,
        "mandatory_external_tool": bool(triggers) or cri >= .6,
        "mandatory_reasons": sorted(triggers),
        "required_independent_verification": cri >= .4,
        "required_human_review": cri >= .8,
        "scale_class": "UNKNOWN",
        "decision_matrix": {},
        "engine": "compatible-fallback",
    }
