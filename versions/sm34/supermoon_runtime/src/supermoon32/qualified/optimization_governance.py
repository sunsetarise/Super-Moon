from __future__ import annotations
import numpy as np
from ..core import InvalidInput

def constraint_violation(inequalities=(),equalities=(),eq_tol=0.0):
    g=np.asarray(list(inequalities),float);h=np.asarray(list(equalities),float);return float(np.sum(np.maximum(g,0.0))+np.sum(np.maximum(np.abs(h)-float(eq_tol),0.0)))

def verify_candidate(x,objective,constraints=(),equalities=(),eq_tol=1e-8):
    x=np.asarray(x,float);obj=float(objective(x));g=[float(fn(x)) for fn in constraints];h=[float(fn(x)) for fn in equalities];v=constraint_violation(g,h,eq_tol);return {'objective':obj,'inequalities':g,'equalities':h,'constraint_violation':v,'feasible':v<=1e-12}

def pareto_nondominated(objectives):
    A=np.asarray(objectives,float)
    if A.ndim!=2 or len(A)==0:raise InvalidInput('objectives must be non-empty 2-D array')
    keep=[]
    for i,a in enumerate(A):
        dominated=any(j!=i and np.all(b<=a) and np.any(b<a) for j,b in enumerate(A))
        if not dominated:keep.append(i)
    return np.array(keep,int)

def probabilistic_constraint(values,threshold,direction='le'):
    v=np.asarray(values,float)
    if v.size==0:raise InvalidInput('values required')
    ok=v<=threshold if direction=='le' else v>=threshold if direction=='ge' else None
    if ok is None:raise InvalidInput('direction must be le or ge')
    return {'probability_satisfied':float(np.mean(ok)),'n':int(v.size),'threshold':float(threshold),'direction':direction}
