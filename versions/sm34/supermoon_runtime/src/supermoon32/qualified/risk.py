from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping, Iterable
from .enums import RiskClass, ScaleClass
from ..core import InvalidInput

FIELDS=('criticality','scale','uncertainty','impact','evidence_deficiency','novelty','qualification_deficiency')
DEFAULT_WEIGHTS={
    'criticality':0.20,'scale':0.12,'uncertainty':0.12,'impact':0.20,
    'evidence_deficiency':0.12,'novelty':0.08,'qualification_deficiency':0.16,
}
MANDATORY_TRIGGERS={
    'human_safety','life_critical','regulatory_certification','airworthiness','nuclear_safety',
    'critical_infrastructure','medical_device_regulatory','flight_critical_structure',
    'extreme_nonlinear_structure','very_large_production_cfd','extreme_sparse_distributed',
    'industrial_cad_interoperability','production_gpu_beyond_validation','formal_legal_acceptance',
    'independent_authority_review'
}

@dataclass(frozen=True)
class RiskProfile:
    criticality: float=0.0
    scale: float=0.0
    uncertainty: float=0.0
    impact: float=0.0
    evidence_deficiency: float=0.0
    novelty: float=0.0
    qualification_deficiency: float=0.0
    triggers: frozenset[str]=field(default_factory=frozenset)
    def __post_init__(self):
        for name in FIELDS:
            v=float(getattr(self,name))
            if not 0.0 <= v <= 1.0: raise InvalidInput(f'{name} must be in [0,1]')
        object.__setattr__(self,'triggers',frozenset(str(x) for x in self.triggers))

@dataclass(frozen=True)
class RiskAssessment:
    cri: float
    risk_class: RiskClass
    mandatory_external_tool: bool
    mandatory_reasons: tuple[str,...]
    required_independent_verification: bool
    required_human_review: bool


def validate_weights(weights: Mapping[str,float] | None=None)->dict[str,float]:
    w=dict(DEFAULT_WEIGHTS if weights is None else weights)
    if set(w)!=set(FIELDS): raise InvalidInput('risk weights must contain exactly '+', '.join(FIELDS))
    if any(float(v)<0 for v in w.values()): raise InvalidInput('risk weights must be non-negative')
    s=sum(float(v) for v in w.values())
    if abs(s-1.0)>1e-12: raise InvalidInput(f'risk weights must sum to 1, got {s}')
    return {k:float(v) for k,v in w.items()}

def classify_cri(cri: float)->RiskClass:
    c=float(cri)
    if not 0<=c<=1: raise InvalidInput('CRI must be in [0,1]')
    if c<0.20:return RiskClass.LOW
    if c<0.40:return RiskClass.MODERATE
    if c<0.60:return RiskClass.HIGH
    if c<0.80:return RiskClass.VERY_HIGH
    return RiskClass.CRITICAL

def assess_risk(profile: RiskProfile, weights: Mapping[str,float] | None=None, external_threshold: float=0.60)->RiskAssessment:
    w=validate_weights(weights)
    cri=sum(w[k]*float(getattr(profile,k)) for k in FIELDS)
    rc=classify_cri(cri)
    hit=tuple(sorted(profile.triggers & MANDATORY_TRIGGERS))
    external=bool(hit) or cri>=float(external_threshold)
    independent=external or cri>=0.40
    human=bool(set(hit) & {'human_safety','life_critical','regulatory_certification','airworthiness','nuclear_safety','medical_device_regulatory','flight_critical_structure','formal_legal_acceptance','independent_authority_review'}) or cri>=0.80
    return RiskAssessment(cri,rc,external,hit,independent,human)

def classify_scale(problem_units: float, distributed: bool=False, billion_scale: bool=False)->ScaleClass:
    n=float(problem_units)
    if n<0: raise InvalidInput('problem_units must be non-negative')
    if billion_scale or n>=1e9:return ScaleClass.S7_EXTREME_DISTRIBUTED
    if distributed and n>=1e7:return ScaleClass.S6_LARGE_DISTRIBUTED
    if distributed:return ScaleClass.S5_MULTI_NODE_HPC
    if n>=1e7:return ScaleClass.S4_SINGLE_NODE_HPC
    if n>=1e6:return ScaleClass.S3_MULTICORE_WORKSTATION
    if n>=1e4:return ScaleClass.S2_WORKSTATION
    if n>=100:return ScaleClass.S1_SMALL
    return ScaleClass.S0_TOY

def decision_matrix(risk: RiskClass, scale: ScaleClass)->dict:
    if risk is RiskClass.CRITICAL:
        return {'external_tool':'MANDATORY','independent_verification':True,'human_review':True}
    if scale>=ScaleClass.S6_LARGE_DISTRIBUTED:
        return {'external_tool':'MANDATORY_FOR_SCALE','independent_verification':risk not in (RiskClass.LOW,RiskClass.MODERATE),'human_review':risk in (RiskClass.VERY_HIGH,RiskClass.CRITICAL)}
    if risk is RiskClass.VERY_HIGH:
        return {'external_tool':'MANDATORY','independent_verification':True,'human_review':True}
    if risk is RiskClass.HIGH:
        return {'external_tool':'RECOMMENDED','independent_verification':True,'human_review':False}
    if risk is RiskClass.MODERATE:
        return {'external_tool':'OPTIONAL','independent_verification':True,'human_review':False}
    return {'external_tool':'OPTIONAL','independent_verification':False,'human_review':False}
