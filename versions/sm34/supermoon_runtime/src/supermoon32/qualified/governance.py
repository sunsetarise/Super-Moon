from __future__ import annotations
from dataclasses import dataclass,field,asdict
from .enums import WorkflowMode,ConfidenceClass,QualificationLevel,MaturityLevel
from .risk import RiskAssessment
from ..core import InvalidInput

@dataclass
class ModelCard:
    name:str; purpose:str; equations:list[str]; assumptions:list[str]; validity_domain:dict; solver:str; discretization:str=''; verification:list[str]=field(default_factory=list); validation:list[str]=field(default_factory=list); uncertainty:dict=field(default_factory=dict); limitations:list[str]=field(default_factory=list); maturity:MaturityLevel=MaturityLevel.M0_CONCEPT
@dataclass
class ToolCard:
    tool:str; version:str; domain:str; maturity:str; qualification_context:list[str]=field(default_factory=list); benchmarks:list[str]=field(default_factory=list); limitations:list[str]=field(default_factory=list); integration_status:str='UNKNOWN'; license:str='unknown'; hardware:list[str]=field(default_factory=list); reproduction_status:str='UNKNOWN'
@dataclass
class DecisionCard:
    decision:str; supporting_simulations:list[str]; validation_evidence:list[str]; uncertainty:dict; solver_agreement:str; confidence:ConfidenceClass; reviewer:str|None; limitations:list[str]; required_follow_up:list[str]

@dataclass(frozen=True)
class ModePolicy:
    mode:WorkflowMode; allow_experimental:bool; require_supported_regime:bool; require_reproducible_config:bool; require_human_review_for_high_risk:bool

MODE_POLICIES={
    WorkflowMode.RESEARCH:ModePolicy(WorkflowMode.RESEARCH,True,False,False,False),
    WorkflowMode.PRODUCTION:ModePolicy(WorkflowMode.PRODUCTION,False,True,True,True),
    WorkflowMode.CERTIFICATION_SUPPORT:ModePolicy(WorkflowMode.CERTIFICATION_SUPPORT,False,True,True,True),
}

def review_gates(risk:RiskAssessment,mode:WorkflowMode)->list[str]:
    gates=[]
    if risk.risk_class.value in ('HIGH','VERY_HIGH','CRITICAL'):gates+=['model_review','solver_review','validation_review','uncertainty_review']
    if risk.required_human_review or mode is WorkflowMode.CERTIFICATION_SUPPORT:gates+=['final_decision_review']
    return list(dict.fromkeys(gates))

def enforce_mode(mode:WorkflowMode,experimental:bool,supported_regime:bool,reproducible:bool):
    p=MODE_POLICIES[mode]
    if experimental and not p.allow_experimental:raise InvalidInput(f'experimental capability not allowed in {mode.value}')
    if p.require_supported_regime and not supported_regime:raise InvalidInput('model is outside supported regime')
    if p.require_reproducible_config and not reproducible:raise InvalidInput('reproducible configuration required')
    return True
