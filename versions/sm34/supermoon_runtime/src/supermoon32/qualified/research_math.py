from __future__ import annotations
import math,numpy as np
from ..core import InvalidInput,SingularSystem

def adjoint_gradient(dR_du,dJ_du,dR_dp,dJ_dp):
    A=np.asarray(dR_du,float);j=np.asarray(dJ_du,float);Rp=np.asarray(dR_dp,float);Jp=np.asarray(dJ_dp,float)
    if A.ndim!=2 or A.shape[0]!=A.shape[1] or j.shape!=(A.shape[0],):raise InvalidInput('adjoint system dimensions invalid')
    if Rp.shape[0]!=A.shape[0]:raise InvalidInput('dR_dp leading dimension mismatch')
    try:lam=np.linalg.solve(A.T,j)
    except np.linalg.LinAlgError as e:raise SingularSystem('adjoint Jacobian singular') from e
    grad=Jp-lam@Rp
    return {'lambda':lam,'gradient':np.asarray(grad),'adjoint_residual':float(np.linalg.norm(A.T@lam-j))}

def pod_snapshots(snapshots,energy_fraction=.999):
    X=np.asarray(snapshots,float)
    if X.ndim!=2 or X.size==0:raise InvalidInput('snapshots must be non-empty 2-D matrix')
    if not 0<energy_fraction<=1:raise InvalidInput('energy_fraction must be in (0,1]')
    mean=X.mean(axis=1,keepdims=True);Y=X-mean;U,s,Vt=np.linalg.svd(Y,full_matrices=False);energy=s*s;cum=np.cumsum(energy)/max(float(np.sum(energy)),1e-300);r=int(np.searchsorted(cum,energy_fraction)+1) if np.sum(energy)>0 else 1
    return {'basis':U[:,:r],'singular_values':s,'mean':mean,'rank':r,'captured_energy':float(cum[r-1]) if len(cum) else 1.0}

def dmd(snapshots,rank=None):
    X=np.asarray(snapshots,float)
    if X.ndim!=2 or X.shape[1]<2:raise InvalidInput('DMD requires matrix with at least two snapshots')
    X1=X[:,:-1];X2=X[:,1:];U,s,Vh=np.linalg.svd(X1,full_matrices=False);r=min(len(s),int(rank) if rank is not None else len(s));tol=np.finfo(float).eps*max(X1.shape)*max(s[0] if len(s) else 0,1);r=min(r,int(np.sum(s>tol)))
    if r<=0:raise InvalidInput('DMD snapshot matrix has zero numerical rank')
    Ur=U[:,:r];sr=s[:r];Vr=Vh[:r,:].T;Atilde=Ur.T@X2@Vr@np.diag(1/sr);eigvals,W=np.linalg.eig(Atilde);modes=X2@Vr@np.diag(1/sr)@W;return {'eigenvalues':eigvals,'modes':modes,'rank':r}

def bayesian_grid_calibration(parameter_grid,log_likelihood,log_prior=None):
    x=np.asarray(parameter_grid,float)
    if x.ndim!=1 or x.size==0:raise InvalidInput('parameter_grid must be non-empty 1-D')
    lp=np.array([0.0 if log_prior is None else float(log_prior(v)) for v in x]);ll=np.array([float(log_likelihood(v)) for v in x]);z=lp+ll;finite=np.isfinite(z)
    if not np.any(finite):raise InvalidInput('posterior normalization failed')
    m=np.max(z[finite]);w=np.zeros_like(z);w[finite]=np.exp(z[finite]-m);s=np.sum(w)
    if not np.isfinite(s) or s<=0:raise InvalidInput('posterior normalization failed')
    w/=s;mean=float(np.sum(w*x));cdf=np.cumsum(w);lo=float(x[np.searchsorted(cdf,.025)]);hi=float(x[min(np.searchsorted(cdf,.975),len(x)-1)]);return {'grid':x,'posterior':w,'mean':mean,'map':float(x[int(np.argmax(w))]),'ci95':(lo,hi)}

def mahalanobis(residual,covariance):
    r=np.asarray(residual,float);C=np.asarray(covariance,float)
    if C.shape!=(len(r),len(r)):raise InvalidInput('covariance shape mismatch')
    try:x=np.linalg.solve(C,r)
    except np.linalg.LinAlgError as e:raise SingularSystem('covariance singular') from e
    d2=float(r@x)
    if d2<0 and abs(d2)<1e-12:d2=0.0
    if d2<0:raise InvalidInput('covariance not positive semidefinite for residual')
    return math.sqrt(d2)
