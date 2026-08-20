from __future__ import annotations
from dataclasses import dataclass
import numpy as np, math
from .core import *
try:
    from supermoon31.cfd import euler_1d, sod_initial, primitive, cons, rusanov, hll
except Exception:
    euler_1d=sod_initial=primitive=cons=rusanov=hll=None
@dataclass
class Euler2DResult:
    U: np.ndarray; steps: int; time: float; min_density: float; min_pressure: float; max_cfl: float; conservation: dict

def primitive2d(U,gamma=1.4):
    U=finite_array(U,'U')
    if U.shape[-1]!=4:raise DimensionMismatch('Euler2D state requires [...,4]')
    rho=U[...,0];mx=U[...,1];my=U[...,2];E=U[...,3]
    if np.any(rho<=0):raise NonPhysicalState('density <= 0')
    u=mx/rho;v=my/rho;p=(gamma-1)*(E-.5*rho*(u*u+v*v))
    if np.any(p<=0) or not np.all(np.isfinite(p)):raise NonPhysicalState('pressure <= 0/nonfinite')
    return rho,u,v,p

def cons2d(rho,u,v,p,gamma=1.4):
    rho=np.asarray(rho,float);u=np.asarray(u,float);v=np.asarray(v,float);p=np.asarray(p,float);E=p/(gamma-1)+.5*rho*(u*u+v*v);return np.stack([rho,rho*u,rho*v,E],axis=-1)

def flux_x(U,gamma=1.4):
    rho,u,v,p=primitive2d(U,gamma);E=U[...,3];return np.stack([rho*u,rho*u*u+p,rho*u*v,u*(E+p)],axis=-1)
def flux_y(U,gamma=1.4):
    rho,u,v,p=primitive2d(U,gamma);E=U[...,3];return np.stack([rho*v,rho*u*v,rho*v*v+p,v*(E+p)],axis=-1)
def rusanov_face(UL,UR,axis,gamma=1.4):
    rL,uL,vL,pL=primitive2d(UL,gamma);rR,uR,vR,pR=primitive2d(UR,gamma);cL=np.sqrt(gamma*pL/rL);cR=np.sqrt(gamma*pR/rR);FL=flux_x(UL,gamma) if axis==0 else flux_y(UL,gamma);FR=flux_x(UR,gamma) if axis==0 else flux_y(UR,gamma);velL=uL if axis==0 else vL;velR=uR if axis==0 else vR;s=np.maximum(np.abs(velL)+cL,np.abs(velR)+cR);return .5*(FL+FR)-.5*s[...,None]*(UR-UL)
def euler_2d_cartesian(U0,dx,dy,t_end,cfl=.4,gamma=1.4,max_steps=100000,periodic=True):
    U=finite_array(U0,'U0').copy();dx=float(dx);dy=float(dy);t_end=float(t_end)
    if U.ndim!=3 or U.shape[-1]!=4 or min(U.shape[:2])<2 or dx<=0 or dy<=0 or t_end<0:raise InvalidInput('invalid 2-D Euler grid')
    init=np.sum(U,axis=(0,1))*dx*dy;t=0.;steps=0;maxcfl=0.;mr=math.inf;mp=math.inf
    while t<t_end-1e-15:
        rho,u,v,p=primitive2d(U,gamma);c=np.sqrt(gamma*p/rho);speedx=float(np.max(np.abs(u)+c));speedy=float(np.max(np.abs(v)+c));dt=cfl/(speedx/dx+speedy/dy);dt=min(dt,t_end-t)
        if not math.isfinite(dt) or dt<=0:raise CFLViolation('invalid timestep')
        if periodic:
            Fx=rusanov_face(U,np.roll(U,-1,axis=1),0,gamma);Fy=rusanov_face(U,np.roll(U,-1,axis=0),1,gamma);U=U-dt/dx*(Fx-np.roll(Fx,1,axis=1))-dt/dy*(Fy-np.roll(Fy,1,axis=0))
        else:
            Ug=np.pad(U,((1,1),(1,1),(0,0)),mode='edge');Fx=rusanov_face(Ug[:, :-1],Ug[:,1:],0,gamma);Fy=rusanov_face(Ug[:-1],Ug[1:],1,gamma);U=U-dt/dx*(Fx[1:-1,1:]-Fx[1:-1,:-1])-dt/dy*(Fy[1:,1:-1]-Fy[:-1,1:-1])
        rho,u,v,p=primitive2d(U,gamma);mr=min(mr,float(rho.min()));mp=min(mp,float(p.min()));maxcfl=max(maxcfl,float(dt*(speedx/dx+speedy/dy)));t+=dt;steps+=1
        if steps>max_steps:raise ConvergenceFailure('max_steps exceeded')
    final=np.sum(U,axis=(0,1))*dx*dy;cons_err={k:float(abs(final[i]-init[i])) for i,k in enumerate(['mass','momentum_x','momentum_y','energy'])}
    return Euler2DResult(U,steps,t,mr,mp,maxcfl,cons_err)

def navier_stokes_viscous_flux_2d(grad_u,grad_v,grad_T,mu,kappa):
    gu=finite_array(grad_u,'grad_u',1);gv=finite_array(grad_v,'grad_v',1);gT=finite_array(grad_T,'grad_T',1)
    if len(gu)!=2 or len(gv)!=2 or len(gT)!=2:raise DimensionMismatch('2-D gradients required')
    div=gu[0]+gv[1];tau_xx=mu*(2*gu[0]-2*div/3);tau_yy=mu*(2*gv[1]-2*div/3);tau_xy=mu*(gu[1]+gv[0]);q=-kappa*gT
    return {'tau':np.array([[tau_xx,tau_xy],[tau_xy,tau_yy]]),'heat_flux':q}
