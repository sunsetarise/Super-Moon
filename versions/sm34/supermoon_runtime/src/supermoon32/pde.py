from __future__ import annotations
import numpy as np
from .core import *

def heat_1d_explicit(u0,alpha,dx,dt,steps,left=None,right=None):
    u=finite_array(u0,'u0',1).copy();alpha=float(alpha);dx=float(dx);dt=float(dt);steps=int(steps)
    if len(u)<3 or alpha<=0 or dx<=0 or dt<=0 or steps<0:raise InvalidInput('invalid heat parameters')
    r=alpha*dt/dx**2
    if r>.5+1e-15:raise CFLViolation(f'explicit heat scheme unstable: r={r}')
    hist=[u.copy()]
    for _ in range(steps):
        v=u.copy();v[1:-1]=u[1:-1]+r*(u[2:]-2*u[1:-1]+u[:-2]);v[0]=u[0] if left is None else float(left);v[-1]=u[-1] if right is None else float(right);u=v;hist.append(u.copy())
    return np.array(hist)

def poisson_1d_dirichlet(f,x,u_left=0.,u_right=0.):
    x=finite_array(x,'x',1);n=len(x)
    if n<3:raise InvalidInput('at least 3 grid points required')
    h=np.diff(x)
    if not np.allclose(h,h[0],rtol=1e-10,atol=1e-14):raise InvalidInput('uniform grid required')
    rhs=np.asarray(f(x[1:-1]) if callable(f) else f,float)
    if rhs.shape!=(n-2,):raise DimensionMismatch('rhs must match interior grid')
    dx=h[0];A=np.diag(np.full(n-2,2.0))+np.diag(np.full(n-3,-1.0),1)+np.diag(np.full(n-3,-1.0),-1);b=rhs*dx*dx;b[0]+=u_left;b[-1]+=u_right;ui=np.linalg.solve(A,b);u=np.r_[u_left,ui,u_right];return u

def linear_advection_1d(u0,c,dx,dt,steps,periodic=True):
    u=finite_array(u0,'u0',1).copy();nu=abs(float(c))*float(dt)/float(dx)
    if nu>1+1e-15:raise CFLViolation('upwind CFL > 1')
    for _ in range(int(steps)):
        if c>=0:prev=np.roll(u,1);v=u-nu*(u-prev)
        else:nxt=np.roll(u,-1);v=u-nu*(u-nxt)
        if not periodic:v[0]=u[0];v[-1]=u[-1]
        u=v
    return u
