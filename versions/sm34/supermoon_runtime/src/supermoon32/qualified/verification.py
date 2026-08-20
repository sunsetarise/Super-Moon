from __future__ import annotations
from dataclasses import dataclass
import math, numpy as np
from .enums import ConfidenceClass
from ..core import InvalidInput
from ..validation import error_norms

@dataclass(frozen=True)
class Discrepancy:
    relative:float; classification:str; absolute:float

def discrepancy(a,b,minor=0.01,significant=0.05,critical=0.20,eps=1e-30)->Discrepancy:
    a=float(a);b=float(b);ae=abs(a-b);r=ae/max(abs(a),abs(b),eps)
    cls='AGREEMENT' if r<minor else 'MINOR_DISCREPANCY' if r<significant else 'SIGNIFICANT_DISCREPANCY' if r<critical else 'CRITICAL_DISCREPANCY'
    return Discrepancy(r,cls,ae)

def observed_order(e_coarse,e_fine,ratio=2.0):
    if min(e_coarse,e_fine,ratio)<=0 or ratio==1:raise InvalidInput('errors and refinement ratio must be positive, ratio != 1')
    return math.log(e_coarse/e_fine)/math.log(ratio)

def richardson_extrapolate(phi_fine,phi_coarse,ratio,order):
    den=ratio**order-1
    if abs(den)<1e-15:raise InvalidInput('invalid Richardson denominator')
    return float(phi_fine+(phi_fine-phi_coarse)/den)

def grid_convergence_index(phi_fine,phi_coarse,ratio,order,safety_factor=1.25,eps=1e-30):
    if ratio<=1 or order<=0:raise InvalidInput('ratio>1 and order>0 required')
    rel=abs(phi_fine-phi_coarse)/max(abs(phi_fine),eps)
    return float(safety_factor*rel/(ratio**order-1))

def linear_residual(A,x,b):
    A=np.asarray(A,float);x=np.asarray(x,float);b=np.asarray(b,float)
    if A.ndim!=2 or x.ndim!=1 or b.ndim!=1 or A.shape!=(len(b),len(x)):raise InvalidInput('incompatible residual dimensions')
    r=b-A@x;return {'vector':r,'L2':float(np.linalg.norm(r)),'Linf':float(np.max(np.abs(r)))}

def validation_metrics(predicted,observed):
    p=np.asarray(predicted,float);o=np.asarray(observed,float)
    if p.shape!=o.shape or p.size==0:raise InvalidInput('predicted/observed must be non-empty and same shape')
    d=p-o
    return {'bias':float(np.mean(d)),'rmse':float(np.sqrt(np.mean(d*d))),'mae':float(np.mean(np.abs(d))),'relative_l2':float(np.linalg.norm(d)/max(np.linalg.norm(o),1e-30)),'correlation':float(np.corrcoef(p.ravel(),o.ravel())[0,1]) if p.size>1 and np.std(p)>0 and np.std(o)>0 else math.nan}

def confidence_score(verification:float,validation:float,convergence:float,uncertainty_control:float,solver_agreement:float,reproducibility:float,qualification:float,data_quality:float)->tuple[float,ConfidenceClass]:
    vals=np.asarray([verification,validation,convergence,uncertainty_control,solver_agreement,reproducibility,qualification,data_quality],float)
    if np.any((vals<0)|(vals>1)):raise InvalidInput('confidence factors must be in [0,1]')
    # Harmonic mean penalizes one weak link more than arithmetic averaging.
    score=0.0 if np.any(vals==0) else float(len(vals)/np.sum(1/vals))
    cls=ConfidenceClass.C0_UNASSESSED if score<.15 else ConfidenceClass.C1_EXPLORATORY if score<.35 else ConfidenceClass.C2_VERIFIED if score<.55 else ConfidenceClass.C3_VALIDATED if score<.70 else ConfidenceClass.C4_MULTI_SOLVER_CONFIRMED if score<.82 else ConfidenceClass.C5_EXTERNALLY_REPRODUCED if score<.93 else ConfidenceClass.C6_QUALIFIED_DEFINED_CONTEXT
    return score,cls
