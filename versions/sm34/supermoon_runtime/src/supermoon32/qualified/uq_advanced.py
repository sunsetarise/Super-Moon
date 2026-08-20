from __future__ import annotations
import math,numpy as np
from ..core import InvalidInput
from ..uq import latin_hypercube

def transform_lhs_unit(samples,bounds):
    X=np.asarray(samples,float);B=np.asarray(bounds,float)
    if X.ndim!=2 or B.shape!=(X.shape[1],2):raise InvalidInput('bounds must be (d,2)')
    if np.any(B[:,1]<=B[:,0]):raise InvalidInput('upper bounds must exceed lower bounds')
    if np.any((X<0)|(X>1)):raise InvalidInput('unit samples must lie in [0,1]')
    return B[:,0]+X*(B[:,1]-B[:,0])

def lhs_samples(n,bounds,seed=0):
    B=np.asarray(bounds,float);return transform_lhs_unit(latin_hypercube(n,len(B),seed),B)

def local_sensitivity(fn,x,relative_step=1e-6,method='central'):
    x=np.asarray(x,float)
    if x.ndim!=1 or x.size==0 or not np.all(np.isfinite(x)):raise InvalidInput('x must be finite vector')
    g=np.empty_like(x)
    for i in range(len(x)):
        h=relative_step*max(1.0,abs(x[i]))
        if method=='central':
            xp=x.copy();xm=x.copy();xp[i]+=h;xm[i]-=h;g[i]=(float(fn(xp))-float(fn(xm)))/(2*h)
        elif method=='forward':
            xp=x.copy();xp[i]+=h;g[i]=(float(fn(xp))-float(fn(x)))/h
        else:raise InvalidInput('method must be central or forward')
    return g

def complex_step_gradient(fn,x,h=1e-30):
    x=np.asarray(x,float);g=np.empty_like(x)
    for i in range(len(x)):
        z=x.astype(complex);z[i]+=1j*h;g[i]=np.imag(fn(z))/h
    return g

def reliability_monte_carlo(limit_state,sampler,n,seed=0):
    if int(n)<=0:raise InvalidInput('n must be positive')
    rng=np.random.default_rng(seed);fail=0;gvals=[]
    for _ in range(int(n)):
        g=float(limit_state(sampler(rng)));gvals.append(g);fail+=g<=0
    pf=fail/int(n);se=math.sqrt(max(pf*(1-pf)/int(n),0.0))
    return {'probability_failure':pf,'standard_error':se,'failures':fail,'n':int(n),'seed':seed,'g_values':np.array(gvals)}

def robust_objective(samples,values,risk_weight=1.0):
    v=np.asarray(values,float)
    if v.size==0:raise InvalidInput('values required')
    return float(np.mean(v)+float(risk_weight)*np.std(v,ddof=1 if len(v)>1 else 0))
