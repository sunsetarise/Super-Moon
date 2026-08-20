from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from scipy.stats import qmc

def optimize(fun,x0,bounds=None,constraints=(),method='SLSQP',jac=None,options=None): return minimize(fun,np.asarray(x0,float),bounds=bounds,constraints=constraints,method=method,jac=jac,options=options or {'maxiter':500,'ftol':1e-10})
def pareto_mask(F):
    F=np.asarray(F,float); keep=np.ones(len(F),bool)
    for i in range(len(F)):
        if not keep[i]: continue
        dominated=np.all(F<=F[i],axis=1)&np.any(F<F[i],axis=1); keep[i]=not np.any(dominated)
    return keep
def latin_hypercube(n,d,seed=0): return qmc.LatinHypercube(d,seed=seed).random(n)
def sobol(n,d,seed=0):
    m=int(np.ceil(np.log2(max(n,1)))); return qmc.Sobol(d,scramble=True,seed=seed).random_base2(m)[:n]
def robust_objective(samples,lam=1.0):
    s=np.asarray(samples,float);return float(np.mean(s)+lam*np.std(s,ddof=1 if len(s)>1 else 0))
def failure_probability(g):
    g=np.asarray(g,float);return float(np.mean(g<=0))


# ================= CELESTIAL DEPTH: optimizer/sampling domain contracts =================
def optimize(fun,x0,bounds=None,constraints=(),method='SLSQP',jac=None,options=None):
    x0=np.asarray(x0,float)
    if x0.ndim!=1 or x0.size==0 or not np.all(np.isfinite(x0)): raise ValueError('x0 must be a finite non-empty vector')
    if bounds is not None and len(bounds)!=len(x0): raise ValueError('bounds length must match x0')
    def checked_fun(x):
        y=float(fun(np.asarray(x,float)))
        if not np.isfinite(y): raise FloatingPointError('objective returned NaN/Inf')
        return y
    return minimize(checked_fun,x0,bounds=bounds,constraints=constraints,method=method,jac=jac,options=options or {'maxiter':500,'ftol':1e-10})

def pareto_mask(F):
    F=np.asarray(F,float)
    if F.ndim!=2 or F.shape[0]==0 or F.shape[1]==0 or not np.all(np.isfinite(F)): raise ValueError('F must be a finite non-empty 2-D objective matrix')
    keep=np.ones(len(F),bool)
    for i in range(len(F)):
        dominated_by_other=np.all(F<=F[i],axis=1)&np.any(F<F[i],axis=1)
        keep[i]=not bool(np.any(dominated_by_other))
    return keep

def latin_hypercube(n,d,seed=0):
    n=int(n);d=int(d)
    if n<=0 or d<=0: raise ValueError('n and d must be positive integers')
    return qmc.LatinHypercube(d,seed=seed).random(n)
def sobol(n,d,seed=0):
    n=int(n);d=int(d)
    if n<=0 or d<=0: raise ValueError('n and d must be positive integers')
    m=int(np.ceil(np.log2(n))); return qmc.Sobol(d,scramble=True,seed=seed).random_base2(m)[:n]
def robust_objective(samples,lam=1.0):
    s=np.asarray(samples,float);lam=float(lam)
    if s.size==0 or not np.all(np.isfinite(s)) or not np.isfinite(lam): raise ValueError('finite non-empty samples and finite lambda required')
    return float(np.mean(s)+lam*np.std(s,ddof=1 if len(s)>1 else 0))
def failure_probability(g):
    g=np.asarray(g,float)
    if g.size==0 or not np.all(np.isfinite(g)): raise ValueError('finite non-empty limit-state samples required')
    return float(np.mean(g<=0))
