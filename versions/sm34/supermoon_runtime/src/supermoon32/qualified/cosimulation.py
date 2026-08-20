from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..core import InvalidInput,ConvergenceFailure

@dataclass
class CouplingResult:
    state_a:object; state_b:object; converged:bool; iterations:int; residual_history:list[float]

def fixed_point_cosim(step_a,step_b,a0,b0,tol=1e-8,max_iter=100,relaxation=1.0):
    if not 0<relaxation<=1:raise InvalidInput('relaxation must be in (0,1]')
    a=np.asarray(a0,float);b=np.asarray(b0,float);hist=[]
    for k in range(1,max_iter+1):
        anew=np.asarray(step_a(b),float);bnew=np.asarray(step_b(anew),float);ar=(1-relaxation)*a+relaxation*anew;br=(1-relaxation)*b+relaxation*bnew;r=max(float(np.linalg.norm(ar-a)),float(np.linalg.norm(br-b)));hist.append(r);a,b=ar,br
        if r<=tol:return CouplingResult(a,b,True,k,hist)
    return CouplingResult(a,b,False,max_iter,hist)

def conservative_transfer_error(source_values,target_values,source_weights=None,target_weights=None):
    s=np.asarray(source_values,float);t=np.asarray(target_values,float);sw=np.ones_like(s) if source_weights is None else np.asarray(source_weights,float);tw=np.ones_like(t) if target_weights is None else np.asarray(target_weights,float)
    if s.shape!=sw.shape or t.shape!=tw.shape:raise InvalidInput('transfer weights shape mismatch')
    qs=float(np.sum(s*sw));qt=float(np.sum(t*tw));return {'source_total':qs,'target_total':qt,'absolute_error':abs(qt-qs),'relative_error':abs(qt-qs)/max(abs(qs),1e-30)}
