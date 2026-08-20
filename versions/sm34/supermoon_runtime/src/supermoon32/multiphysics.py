from __future__ import annotations
import numpy as np,time
from .core import *

def fixed_point_coupling(update_x,update_y,x0,y0,tol=1e-9,max_iter=200,relaxation=.5):
    x=np.asarray(x0,float).copy();y=np.asarray(y0,float).copy();hist=[];t=time.perf_counter();w=float(relaxation)
    if not 0<w<=1:raise InvalidInput('relaxation must be in (0,1]')
    for k in range(max_iter+1):
        xn=np.asarray(update_x(x,y),float);yn=np.asarray(update_y(xn,y),float);rx=float(np.linalg.norm(xn-x));ry=float(np.linalg.norm(yn-y));r=max(rx,ry);hist.append(r)
        if r<=tol:return SolverResult((x,y),True,k,r,'coupling_tolerance',time.perf_counter()-t,{'x_residual':rx,'y_residual':ry},hist)
        if k==max_iter:break
        x=(1-w)*x+w*xn;y=(1-w)*y+w*yn
    return SolverResult((x,y),False,max_iter,hist[-1],'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')
def conservative_transfer(source_values,source_weights,target_weights):
    s=finite_array(source_values,'source_values',1);sw=finite_array(source_weights,'source_weights',1);tw=finite_array(target_weights,'target_weights',1)
    if len(s)!=len(sw):raise DimensionMismatch('source values/weights mismatch')
    total=float(s@sw)
    if np.any(tw<0) or np.sum(tw)<=0:raise InvalidInput('positive target weights required')
    # Constant target density that preserves integrated quantity exactly.
    out=np.full(len(tw),total/np.sum(tw));return out,{'source_total':total,'target_total':float(out@tw),'error':float(abs(out@tw-total))}
