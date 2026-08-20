from __future__ import annotations
import numpy as np, math
from .core import *

def latin_hypercube(n,d,seed=0):
    n=int(n);d=int(d)
    if n<=0 or d<=0:raise InvalidInput('n,d positive')
    rng=np.random.default_rng(seed);u=rng.random((n,d));X=np.empty((n,d))
    for j in range(d):X[:,j]=(rng.permutation(n)+u[:,j])/n
    return X
def monte_carlo(fn,sampler,n,seed=0):
    rng=np.random.default_rng(seed);vals=[]
    for _ in range(int(n)):vals.append(float(fn(sampler(rng))))
    a=np.array(vals);mean=float(np.mean(a));std=float(np.std(a,ddof=1)) if len(a)>1 else 0.;se=std/math.sqrt(len(a)) if len(a) else math.nan;return {'mean':mean,'std':std,'standard_error':se,'ci95':(mean-1.96*se,mean+1.96*se),'n':len(a),'seed':seed,'values':a}
def bootstrap(data,stat=np.mean,n_resamples=1000,seed=0):
    x=finite_array(data,'data',1);rng=np.random.default_rng(seed);v=np.array([stat(rng.choice(x,len(x),replace=True)) for _ in range(int(n_resamples))],float);return {'estimate':float(stat(x)),'bias':float(np.mean(v)-stat(x)),'ci95':tuple(np.quantile(v,[.025,.975])),'samples':v,'seed':seed}
def sobol_first_order(model,bounds,n=2000,seed=0):
    # Saltelli-style first-order estimator for independent uniform variables.
    rng=np.random.default_rng(seed);bounds=np.asarray(bounds,float);d=len(bounds);A=rng.random((n,d));B=rng.random((n,d));lo=bounds[:,0];hi=bounds[:,1];A=lo+(hi-lo)*A;B=lo+(hi-lo)*B;fA=np.array([model(x) for x in A],float);fB=np.array([model(x) for x in B],float);V=np.var(np.r_[fA,fB],ddof=1)
    if V<=np.finfo(float).tiny:raise InvalidInput('zero output variance')
    S=[]
    for i in range(d):C=A.copy();C[:,i]=B[:,i];fC=np.array([model(x) for x in C],float);S.append(float(np.mean(fB*(fC-fA))/V))
    return np.array(S)
