from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
from .enums import QualificationLevel, ScaleClass, RiskClass
from .risk import RiskAssessment, decision_matrix
from .tools import QualifiedToolRegistry, QualifiedTool
from ..core import InvalidInput

@dataclass(frozen=True)
class SolverCandidate:
    name:str; domain:str; internal:bool
    expected_error:float=0.0; runtime_cost:float=0.0; memory_cost:float=0.0; qualification_risk:float=0.0; model_mismatch:float=0.0; reproducibility_risk:float=0.0
    qualification_level:QualificationLevel=QualificationLevel.Q0_UNKNOWN
    verified_scale:ScaleClass=ScaleClass.S2_WORKSTATION
    evidence:tuple[str,...]=()
    def objective(self,weights=(.30,.15,.10,.20,.15,.10)):
        vals=(self.expected_error,self.runtime_cost,self.memory_cost,self.qualification_risk,self.model_mismatch,self.reproducibility_risk)
        if len(weights)!=6 or any(float(w)<0 for w in weights):raise InvalidInput('invalid solver objective weights')
        s=sum(weights)
        if s<=0:raise InvalidInput('solver objective weights sum must be positive')
        return sum(float(w)*float(v) for w,v in zip(weights,vals))/s

@dataclass
class RouteRequest:
    domain:str; risk:RiskAssessment; scale:ScaleClass
    minimum_external_qualification:QualificationLevel=QualificationLevel.Q2_TESTED
    required_accuracy:float|None=None
    certification_required:bool=False
    independent_verification_required:bool=False

@dataclass
class RouteDecision:
    primary:str|None
    external_tool:str|None
    verification_solver:str|None
    external_mandatory:bool
    human_review:bool
    rationale:list[str]=field(default_factory=list)
    candidate_scores:dict[str,float]=field(default_factory=dict)

class SolverRoutingEngine:
    def __init__(self, registry:QualifiedToolRegistry|None=None):self.registry=registry or QualifiedToolRegistry()
    def route(self,request:RouteRequest,candidates:Iterable[SolverCandidate])->RouteDecision:
        c=[x for x in candidates if x.domain.lower()==request.domain.lower()]
        if not c:raise InvalidInput(f'no solver candidates for domain {request.domain}')
        policy=decision_matrix(request.risk.risk_class,request.scale)
        external_mandatory=request.risk.mandatory_external_tool or request.certification_required or policy['external_tool'].startswith('MANDATORY')
        internal=[x for x in c if x.internal and x.verified_scale>=request.scale]
        scores={x.name:x.objective() for x in c}
        primary=min(internal,key=lambda x:scores[x.name]).name if internal else None
        minq=max(request.minimum_external_qualification,QualificationLevel.Q5_CERTIFICATION_ACCEPTABLE if request.certification_required else QualificationLevel.Q0_UNKNOWN)
        ext=self.registry.best(request.domain,minq) if external_mandatory else self.registry.best(request.domain,request.minimum_external_qualification)
        if external_mandatory and ext is None:
            rationale=['qualified external tool is mandatory but none meets the required registry qualification']
            return RouteDecision(primary,None,None,True,request.risk.required_human_review or request.certification_required,rationale,scores)
        verify_needed=request.independent_verification_required or request.risk.required_independent_verification
        verification=None
        if verify_needed:
            alternatives=[x for x in c if x.name!=primary]
            if ext and ext.tool_name!=primary:verification=ext.tool_name
            elif alternatives:verification=min(alternatives,key=lambda x:scores[x.name]).name
        rationale=[f'CRI={request.risk.cri:.4f} ({request.risk.risk_class.value})',f'scale={request.scale.name}',f'external={"mandatory" if external_mandatory else "optional"}']
        return RouteDecision(primary,ext.tool_name if ext else None,verification,external_mandatory,request.risk.required_human_review or request.certification_required,rationale,scores)

def pareto_front(candidates:Iterable[SolverCandidate])->list[SolverCandidate]:
    c=list(candidates);out=[]
    for a in c:
        va=(a.expected_error,a.runtime_cost,a.memory_cost,a.qualification_risk,a.model_mismatch,a.reproducibility_risk)
        dominated=False
        for b in c:
            if a is b:continue
            vb=(b.expected_error,b.runtime_cost,b.memory_cost,b.qualification_risk,b.model_mismatch,b.reproducibility_risk)
            if all(x<=y for x,y in zip(vb,va)) and any(x<y for x,y in zip(vb,va)):dominated=True;break
        if not dominated:out.append(a)
    return out
