from __future__ import annotations
from dataclasses import dataclass
import numpy as np
@dataclass
class CFDResult:
    x:np.ndarray; U:np.ndarray; residual_history:list; metadata:dict

def primitive(U,gamma=1.4):
    rho=U[...,0]; u=U[...,1]/rho; E=U[...,2]/rho; p=(gamma-1)*rho*(E-.5*u*u); return rho,u,p

def cons(rho,u,p,gamma=1.4): return np.stack([rho,rho*u,p/(gamma-1)+.5*rho*u*u],axis=-1)
def flux(U,gamma=1.4):
    rho,u,p=primitive(U,gamma); return np.stack([rho*u,rho*u*u+p,u*(U[...,2]+p)],axis=-1)
def rusanov(UL,UR,gamma=1.4):
    FL,FR=flux(UL,gamma),flux(UR,gamma); rl,ul,pl=primitive(UL,gamma);rr,ur,pr=primitive(UR,gamma); aL=np.sqrt(gamma*pl/rl);aR=np.sqrt(gamma*pr/rr);s=np.maximum(np.abs(ul)+aL,np.abs(ur)+aR);return .5*(FL+FR)-.5*s[...,None]*(UR-UL)
def hll(UL,UR,gamma=1.4):
    FL,FR=flux(UL,gamma),flux(UR,gamma); rl,ul,pl=primitive(UL,gamma);rr,ur,pr=primitive(UR,gamma); aL=np.sqrt(gamma*pl/rl);aR=np.sqrt(gamma*pr/rr);SL=np.minimum(ul-aL,ur-aR);SR=np.maximum(ul+aL,ur+aR)
    F=(SR[...,None]*FL-SL[...,None]*FR+SL[...,None]*SR[...,None]*(UR-UL))/np.maximum((SR-SL)[...,None],1e-300); return np.where((SL>=0)[...,None],FL,np.where((SR<=0)[...,None],FR,F))
def minmod(a,b): return np.where(a*b<=0,0,np.sign(a)*np.minimum(abs(a),abs(b)))
def reconstruct(U):
    dL=U[1:-1]-U[:-2];dR=U[2:]-U[1:-1];s=minmod(dL,dR); UL=U[1:-2]+.5*s[:-1];UR=U[2:-1]-.5*s[1:];return UL,UR

def euler_1d(x,U0,t_end,cfl=.45,gamma=1.4,scheme='rusanov',second_order=True,max_steps=100000):
    x=np.asarray(x,float);U=np.asarray(U0,float).copy();dx=float(x[1]-x[0]); hist=[];t=0.;steps=0
    while t<t_end and steps<max_steps:
        rho,u,p=primitive(U,gamma)
        if np.any(rho<=0) or np.any(p<=0): raise FloatingPointError('non-positive density/pressure')
        a=np.sqrt(gamma*p/rho);dt=min(cfl*dx/np.max(np.abs(u)+a),t_end-t); old=U.copy(); Ug=np.vstack([U[0],U[0],U,U[-1],U[-1]])
        if second_order:
            UL,UR=reconstruct(Ug); # interfaces enough; align to N+1
            Fi=(rusanov if scheme=='rusanov' else hll)(UL,UR,gamma)
            U=U-dt/dx*(Fi[2:2+len(U)]-Fi[1:1+len(U)])
        else:
            Fi=(rusanov if scheme=='rusanov' else hll)(Ug[1:-1],Ug[2:],gamma); U=U-dt/dx*(Fi[1:len(U)+1]-Fi[:len(U)])
        hist.append(float(np.linalg.norm(U-old)/max(np.linalg.norm(old),1e-300)));t+=dt;steps+=1
    return CFDResult(x,U,hist,{'t':t,'steps':steps,'scheme':scheme,'fidelity':'Level 2 Euler','CFL_target':cfl})
def sod_initial(x,x0=.5,gamma=1.4):
    x=np.asarray(x);rho=np.where(x<x0,1,.125);u=np.zeros_like(x);p=np.where(x<x0,1,.1);return cons(rho,u,p,gamma)

def cavity_flow(nx=33,ny=33,Re=100,dt=.001,steps=100,lid=1.0,pressure_iterations=80):
    # Chorin projection finite-difference reference solver
    dx=1/(nx-1);dy=1/(ny-1);nu=lid/Re;u=np.zeros((ny,nx));v=np.zeros_like(u);p=np.zeros_like(u);hist=[]
    for _ in range(steps):
        un=u.copy();vn=v.copy();
        u[1:-1,1:-1]=un[1:-1,1:-1]-dt*(un[1:-1,1:-1]*(un[1:-1,1:-1]-un[1:-1,:-2])/dx+vn[1:-1,1:-1]*(un[1:-1,1:-1]-un[:-2,1:-1])/dy)+nu*dt*((un[1:-1,2:]-2*un[1:-1,1:-1]+un[1:-1,:-2])/dx**2+(un[2:,1:-1]-2*un[1:-1,1:-1]+un[:-2,1:-1])/dy**2)
        v[1:-1,1:-1]=vn[1:-1,1:-1]-dt*(un[1:-1,1:-1]*(vn[1:-1,1:-1]-vn[1:-1,:-2])/dx+vn[1:-1,1:-1]*(vn[1:-1,1:-1]-vn[:-2,1:-1])/dy)+nu*dt*((vn[1:-1,2:]-2*vn[1:-1,1:-1]+vn[1:-1,:-2])/dx**2+(vn[2:,1:-1]-2*vn[1:-1,1:-1]+vn[:-2,1:-1])/dy**2)
        b=((u[1:-1,2:]-u[1:-1,:-2])/(2*dx)+(v[2:,1:-1]-v[:-2,1:-1])/(2*dy))/dt
        for __ in range(pressure_iterations):
            pn=p.copy();p[1:-1,1:-1]=((pn[1:-1,2:]+pn[1:-1,:-2])*dy**2+(pn[2:,1:-1]+pn[:-2,1:-1])*dx**2-b*dx**2*dy**2)/(2*(dx**2+dy**2));p[:,-1]=p[:,-2];p[:,0]=p[:,1];p[0,:]=p[1,:];p[-1,:]=0
        u[1:-1,1:-1]-=dt*(p[1:-1,2:]-p[1:-1,:-2])/(2*dx);v[1:-1,1:-1]-=dt*(p[2:,1:-1]-p[:-2,1:-1])/(2*dy)
        u[0,:]=0;u[:,0]=0;u[:,-1]=0;u[-1,:]=lid;v[0,:]=v[-1,:]=0;v[:,0]=v[:,-1]=0
        div=(u[1:-1,2:]-u[1:-1,:-2])/(2*dx)+(v[2:,1:-1]-v[:-2,1:-1])/(2*dy);hist.append(float(np.linalg.norm(div)))
    return {'u':u,'v':v,'p':p,'divergence_history':hist,'metadata':{'fidelity':'laminar incompressible Navier-Stokes','Re':Re}}

def sutherland_mu(T,mu0=1.716e-5,T0=273.15,S=110.4): return mu0*(T/T0)**1.5*(T0+S)/(T+S)
def y_plus(rho,u_tau,y,mu): return rho*u_tau*y/mu
def first_cell_height(yplus,rho,u_tau,mu): return yplus*mu/(rho*u_tau)
def smagorinsky_nut(Cs,delta,strain_mag): return (Cs*delta)**2*strain_mag
def wale_nut(Cw,delta,Sd2,S2): return (Cw*delta)**2*(Sd2**1.5)/max(S2**2.5+Sd2**1.25,1e-300)
def k_epsilon_nut(rho,k,eps,Cmu=.09): return Cmu*rho*k*k/max(eps,1e-300)
def k_omega_nut(rho,k,omega): return rho*k/max(omega,1e-300)
def sst_blend(F1,a,b): return F1*a+(1-F1)*b

def boundary_layer_layers(first,growth,n): return first*growth**np.arange(n)
def cfl(U,dt,dx,gamma=1.4):
    r,u,p=primitive(np.asarray(U),gamma);a=np.sqrt(gamma*p/r);return float(np.max((np.abs(u)+a)*dt/dx))


# ================= CELESTIAL DEPTH: CFD positivity / CFL / nonconvergence =================
def _state(U,gamma=1.4,name='U'):
    U=np.asarray(U,float);gamma=float(gamma)
    if gamma<=1 or not np.isfinite(gamma): raise ValueError('gamma must be finite > 1')
    if U.shape[-1]!=3 or not np.all(np.isfinite(U)): raise ValueError(f'{name} must be finite conservative state[...,3]')
    rho=U[...,0]
    if np.any(rho<=0): raise FloatingPointError('INVALID_INPUT: non-positive density')
    u=U[...,1]/rho;p=(gamma-1)*(U[...,2]-.5*rho*u*u)
    if np.any(~np.isfinite(p)) or np.any(p<=0): raise FloatingPointError('INVALID_INPUT: non-positive pressure')
    return U,rho,u,p

def primitive(U,gamma=1.4):
    _,rho,u,p=_state(U,gamma);return rho,u,p

def cons(rho,u,p,gamma=1.4):
    rho=np.asarray(rho,float);u=np.asarray(u,float);p=np.asarray(p,float);gamma=float(gamma)
    try: rho,u,p=np.broadcast_arrays(rho,u,p)
    except ValueError as e: raise ValueError('rho/u/p are not broadcast-compatible') from e
    if gamma<=1 or np.any(~np.isfinite(rho)) or np.any(~np.isfinite(u)) or np.any(~np.isfinite(p)) or np.any(rho<=0) or np.any(p<=0): raise ValueError('finite rho>0, p>0, gamma>1 required')
    return np.stack([rho,rho*u,p/(gamma-1)+.5*rho*u*u],axis=-1)

def flux(U,gamma=1.4):
    U,rho,u,p=_state(U,gamma);return np.stack([rho*u,rho*u*u+p,u*(U[...,2]+p)],axis=-1)

def rusanov(UL,UR,gamma=1.4):
    UL,rl,ul,pl=_state(UL,gamma,'UL');UR,rr,ur,pr=_state(UR,gamma,'UR');FL,FR=flux(UL,gamma),flux(UR,gamma);aL=np.sqrt(gamma*pl/rl);aR=np.sqrt(gamma*pr/rr);s=np.maximum(np.abs(ul)+aL,np.abs(ur)+aR);return .5*(FL+FR)-.5*s[...,None]*(UR-UL)

def hll(UL,UR,gamma=1.4):
    UL,rl,ul,pl=_state(UL,gamma,'UL');UR,rr,ur,pr=_state(UR,gamma,'UR');FL,FR=flux(UL,gamma),flux(UR,gamma);aL=np.sqrt(gamma*pl/rl);aR=np.sqrt(gamma*pr/rr);SL=np.minimum(ul-aL,ur-aR);SR=np.maximum(ul+aL,ur+aR);den=SR-SL
    if np.any(np.abs(den)<=np.finfo(float).tiny): raise FloatingPointError('NUMERICAL_BREAKDOWN: HLL wave-speed denominator collapsed')
    F=(SR[...,None]*FL-SL[...,None]*FR+SL[...,None]*SR[...,None]*(UR-UL))/den[...,None];return np.where((SL>=0)[...,None],FL,np.where((SR<=0)[...,None],FR,F))

def reconstruct(U):
    """MUSCL/minmod reconstruction for a ghost-extended 1-D state array.

    Shape contract: for M cell states, slopes are defined on M-2 interior
    cells and the returned left/right states describe exactly M-3
    interfaces.  In :func:`euler_1d`, ``M=N+4`` (two copied boundary
    cells on each side), therefore reconstruction returns ``N+1``
    interfaces: the two physical boundary faces plus ``N-1`` interior
    faces.
    """
    U=np.asarray(U,float)
    if U.ndim!=2 or U.shape[0]<4 or U.shape[1]!=3 or not np.all(np.isfinite(U)): raise ValueError('finite N x 3 state with N>=4 required')
    dL=U[1:-1]-U[:-2];dR=U[2:]-U[1:-1];s=minmod(dL,dR)
    UL=U[1:-2]+.5*s[:-1];UR=U[2:-1]-.5*s[1:]
    if UL.shape!=UR.shape or UL.shape!=(U.shape[0]-3,U.shape[1]): raise RuntimeError('INVARIANT_VIOLATION: MUSCL interface reconstruction shape mismatch')
    return UL,UR

def euler_1d(x,U0,t_end,cfl=.45,gamma=1.4,scheme='rusanov',second_order=True,max_steps=100000):
    x=np.asarray(x,float);U=np.asarray(U0,float).copy();t_end=float(t_end);cfl=float(cfl);max_steps=int(max_steps);gamma=float(gamma)
    if x.ndim!=1 or len(x)<3 or U.shape!=(len(x),3) or not np.all(np.isfinite(x)): raise ValueError('x must be finite 1-D grid and U0 must be len(x) x 3')
    dxv=np.diff(x)
    if np.any(dxv<=0): raise ValueError('x must be strictly increasing')
    dx=float(dxv[0])
    if not np.allclose(dxv,dx,rtol=1e-10,atol=1e-14*max(1.0,abs(dx))): raise ValueError('current Euler solver requires a uniform grid')
    if t_end<0 or not np.isfinite(t_end) or not 0<cfl<=1 or gamma<=1 or max_steps<1 or scheme not in {'rusanov','hll'}: raise ValueError('invalid t_end/CFL/gamma/max_steps/scheme')
    _state(U,gamma,'U0');hist=[];t=0.;steps=0;solver=rusanov if scheme=='rusanov' else hll
    min_rho=float('inf');min_p=float('inf');max_cfl=0.0
    while t<t_end:
        if steps>=max_steps: raise RuntimeError('NONCONVERGED: max_steps reached before t_end')
        rho,u,p=primitive(U,gamma);a=np.sqrt(gamma*p/rho);speed=float(np.max(np.abs(u)+a))
        if not np.isfinite(speed) or speed<=0: raise FloatingPointError('NUMERICAL_BREAKDOWN: invalid characteristic speed')
        dt=min(cfl*dx/speed,t_end-t)
        if dt<=0 or not np.isfinite(dt): raise FloatingPointError('NUMERICAL_BREAKDOWN: invalid time step')
        old=U.copy();Ug=np.vstack([U[0],U[0],U,U[-1],U[-1]])
        if second_order:
            UL,UR=reconstruct(Ug);Fi=solver(UL,UR,gamma)
            # Fi has N+1 physical-face fluxes.  Cell i is bounded by
            # faces i and i+1, so the finite-volume divergence must pair
            # Fi[1:] with Fi[:-1].  The former Fi[2:2+N]-Fi[1:1+N]
            # mixed an N-1 slice with an N slice and caused the confirmed
            # (59,3) vs (60,3) broadcasting failure for N=60.
            if Fi.shape!=(len(U)+1,3): raise RuntimeError('INVARIANT_VIOLATION: expected N+1 interface fluxes')
            U=U-dt/dx*(Fi[1:]-Fi[:-1])
        else:
            Fi=solver(Ug[1:-1],Ug[2:],gamma);U=U-dt/dx*(Fi[1:len(U)+1]-Fi[:len(U)])
        _,rr,_,pp=_state(U,gamma,'advanced state');min_rho=min(min_rho,float(np.min(rr)));min_p=min(min_p,float(np.min(pp)));max_cfl=max(max_cfl,float(speed*dt/dx))
        hist.append(float(np.linalg.norm(U-old)/max(np.linalg.norm(old),np.finfo(float).tiny)));t+=dt;steps+=1
    return CFDResult(x,U,hist,{'t':t,'steps':steps,'scheme':scheme,'fidelity':'Level 2 Euler','CFL_target':cfl,'CFL_observed_max':max_cfl,'minimum_density':min_rho if steps else float(np.min(U[:,0])),'minimum_pressure':min_p if steps else float(np.min(primitive(U,gamma)[2])),'status':'CONVERGED_TO_T_END'})

_cavity_pre_celestial=cavity_flow
def cavity_flow(nx=33,ny=33,Re=100,dt=.001,steps=100,lid=1.0,pressure_iterations=80):
    nx=int(nx);ny=int(ny);steps=int(steps);pressure_iterations=int(pressure_iterations);Re=float(Re);dt=float(dt);lid=float(lid)
    if nx<3 or ny<3 or steps<0 or pressure_iterations<1 or Re<=0 or dt<=0 or not np.isfinite([Re,dt,lid]).all(): raise ValueError('invalid cavity solver discretization/operating parameters')
    r=_cavity_pre_celestial(nx,ny,Re,dt,steps,lid,pressure_iterations)
    if not all(np.all(np.isfinite(r[k])) for k in ('u','v','p')): raise FloatingPointError('NUMERICAL_BREAKDOWN: cavity solver produced NaN/Inf')
    r['metadata']['final_divergence_norm']=r['divergence_history'][-1] if r['divergence_history'] else 0.0;r['metadata']['steps']=steps;return r

def sutherland_mu(T,mu0=1.716e-5,T0=273.15,S=110.4):
    T,mu0,T0,S=map(float,(T,mu0,T0,S))
    if not np.isfinite([T,mu0,T0,S]).all() or T<=0 or mu0<=0 or T0<=0 or T+S<=0: raise ValueError('invalid Sutherland-law parameters')
    return mu0*(T/T0)**1.5*(T0+S)/(T+S)
def y_plus(rho,u_tau,y,mu):
    rho,u_tau,y,mu=map(float,(rho,u_tau,y,mu))
    if not np.isfinite([rho,u_tau,y,mu]).all() or min(rho,u_tau,y,mu)<0 or mu<=0: raise ValueError('invalid y+ parameters')
    return rho*u_tau*y/mu
def first_cell_height(yplus,rho,u_tau,mu):
    yplus,rho,u_tau,mu=map(float,(yplus,rho,u_tau,mu))
    if not np.isfinite([yplus,rho,u_tau,mu]).all() or min(yplus,rho,u_tau,mu)<=0: raise ValueError('positive finite wall-model parameters required')
    return yplus*mu/(rho*u_tau)
def cfl(U,dt,dx,gamma=1.4):
    dt=float(dt);dx=float(dx)
    if dt<0 or dx<=0 or not np.isfinite([dt,dx]).all(): raise ValueError('finite dt>=0 and dx>0 required')
    r,u,p=primitive(np.asarray(U),gamma);a=np.sqrt(gamma*p/r);return float(np.max((np.abs(u)+a)*dt/dx))
