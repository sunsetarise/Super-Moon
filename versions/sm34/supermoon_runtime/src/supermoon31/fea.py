from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.linalg import eigh
from scipy.sparse import lil_matrix, csr_matrix
from scipy.sparse.linalg import spsolve, eigsh

@dataclass
class LinearResult:
    u:np.ndarray; reactions:np.ndarray; residual_norm:float; condition:float|None=None

def elasticity_matrix(E,nu):
    l=E*nu/((1+nu)*(1-2*nu)); m=E/(2*(1+nu)); C=np.full((6,6),0.0); C[:3,:3]=l; np.fill_diagonal(C[:3,:3],l+2*m); C[3:,3:]=np.eye(3)*m; return C

def tet4_B(X):
    X=np.asarray(X,float); A=np.ones((4,4)); A[:,1:]=X; inv=np.linalg.inv(A); grads=inv[1:,:].T
    B=np.zeros((6,12))
    for i,(dx,dy,dz) in enumerate(grads):
        j=3*i; B[:,j:j+3]=[[dx,0,0],[0,dy,0],[0,0,dz],[dy,dx,0],[0,dz,dy],[dz,0,dx]]
    V=abs(np.linalg.det(np.c_[X[1]-X[0],X[2]-X[0],X[3]-X[0]]))/6
    return B,V

def solve_tet4(nodes,tets,E,nu,loads=None,fixed=None):
    X=np.asarray(nodes,float); tets=np.asarray(tets,int); nd=3*len(X); K=lil_matrix((nd,nd)); C=elasticity_matrix(E,nu)
    for tet in tets:
        B,V=tet4_B(X[tet]); ke=B.T@C@B*V; dof=np.array([[3*i,3*i+1,3*i+2] for i in tet]).ravel()
        for a,I in enumerate(dof):
            for b,J in enumerate(dof): K[I,J]+=ke[a,b]
    K=K.tocsr(); f=np.zeros(nd)
    if loads:
        for dof,val in loads.items(): f[int(dof)]+=float(val)
    fixed=np.array(sorted(set(fixed or [])),int); free=np.setdiff1d(np.arange(nd),fixed); u=np.zeros(nd)
    if len(free): u[free]=spsolve(K[free][:,free],f[free])
    r=K@u-f; return LinearResult(u,r,float(np.linalg.norm(r[free])))

def truss2d(nodes,elements,E,A,loads=None,fixed=None):
    X=np.asarray(nodes,float); nd=2*len(X); K=np.zeros((nd,nd))
    for i,j in elements:
        d=X[j,:2]-X[i,:2]; L=np.linalg.norm(d); c,s=d/L; k=E*A/L*np.array([[c*c,c*s,-c*c,-c*s],[c*s,s*s,-c*s,-s*s],[-c*c,-c*s,c*c,c*s],[-c*s,-s*s,c*s,s*s]])
        ids=[2*i,2*i+1,2*j,2*j+1]; K[np.ix_(ids,ids)]+=k
    f=np.zeros(nd)
    for dof,val in (loads or {}).items(): f[dof]+=val
    fixed=np.array(sorted(set(fixed or [])),int); free=np.setdiff1d(np.arange(nd),fixed); u=np.zeros(nd); u[free]=np.linalg.solve(K[np.ix_(free,free)],f[free]); r=K@u-f
    return LinearResult(u,r,float(np.linalg.norm(r[free])),float(np.linalg.cond(K[np.ix_(free,free)])))

def cst_stiffness(X,E,nu,t=1.0,plane_stress=True):
    X=np.asarray(X,float)[:,:2]; x1,y1=X[0];x2,y2=X[1];x3,y3=X[2]; A=0.5*((x2-x1)*(y3-y1)-(x3-x1)*(y2-y1));
    if A<=0: raise ValueError('triangle orientation/area invalid')
    b=np.array([y2-y3,y3-y1,y1-y2]); c=np.array([x3-x2,x1-x3,x2-x1]); B=np.zeros((3,6))
    for i in range(3): B[:,2*i:2*i+2]=[[b[i],0],[0,c[i]],[c[i],b[i]]]
    B/=2*A
    if plane_stress: D=E/(1-nu**2)*np.array([[1,nu,0],[nu,1,0],[0,0,(1-nu)/2]])
    else: D=E/((1+nu)*(1-2*nu))*np.array([[1-nu,nu,0],[nu,1-nu,0],[0,0,(1-2*nu)/2]])
    return t*A*(B.T@D@B),B,D,A

def newmark(M,C,K,f,dt,n,u0=None,v0=None,beta=.25,gamma=.5):
    M=np.asarray(M,float);C=np.asarray(C,float);K=np.asarray(K,float); nDOF=M.shape[0]; u=np.zeros((n+1,nDOF));v=u.copy();a=u.copy();u[0]=0 if u0 is None else u0;v[0]=0 if v0 is None else v0
    force=lambda k: np.asarray(f(k*dt) if callable(f) else f,float)
    a[0]=np.linalg.solve(M,force(0)-C@v[0]-K@u[0]); Aeff=M+gamma*dt*C+beta*dt*dt*K
    for k in range(n):
        up=u[k]+dt*v[k]+dt*dt*(.5-beta)*a[k]; vp=v[k]+dt*(1-gamma)*a[k]; a[k+1]=np.linalg.solve(Aeff,force(k+1)-C@vp-K@up); u[k+1]=up+beta*dt*dt*a[k+1];v[k+1]=vp+gamma*dt*a[k+1]
    return u,v,a

def modal(K,M,n_modes=6):
    K=np.asarray(K,float);M=np.asarray(M,float); w2,V=eigh(K,M); idx=np.argsort(w2); w2=w2[idx];V=V[:,idx]; mask=w2>1e-12; return np.sqrt(w2[mask][:n_modes]),V[:,mask][:,:n_modes]
def buckling(K,Kg,n_modes=6):
    vals,V=eigh(np.asarray(K,float),-np.asarray(Kg,float)); ok=np.isfinite(vals)&(vals>0); idx=np.argsort(vals[ok]); return vals[ok][idx][:n_modes],V[:,ok][:,idx][:,:n_modes]

def thermal_bar(length,n,k,A,q=0,T0=0,T1=1):
    x=np.linspace(0,length,n+1); K=np.zeros((n+1,n+1)); f=np.zeros(n+1)
    for e in range(n):
        h=x[e+1]-x[e]; ke=k*A/h*np.array([[1,-1],[-1,1]]); fe=q*A*h/2*np.ones(2); ids=[e,e+1];K[np.ix_(ids,ids)]+=ke;f[ids]+=fe
    fixed=[0,n]; free=np.arange(1,n); T=np.zeros(n+1);T[0]=T0;T[-1]=T1; f2=f-K@T;T[free]=np.linalg.solve(K[np.ix_(free,free)],f2[free]); return x,T

def j2_radial_return(strain_inc,stress_old,ep_old,E,nu,sigy,H=0):
    de=np.asarray(strain_inc,float); s0=np.asarray(stress_old,float); C=elasticity_matrix(E,nu); trial=s0+C@de; mean=trial[:3].mean(); dev=trial.copy();dev[:3]-=mean; seq=np.sqrt(1.5*(dev[:3]@dev[:3]+2*dev[3:]@dev[3:])); f=seq-(sigy+H*ep_old)
    if f<=0:return trial,ep_old,C,False
    G=E/(2*(1+nu)); dgamma=f/(3*G+H); scale=max(0,1-3*G*dgamma/max(seq,1e-300)); dev*=scale; stress=dev;stress[:3]+=mean; dep=np.sqrt(2/3)*dgamma; return stress,ep_old+dep,C,True

def penalty_contact(gap,penalty): return (0.0,0.0) if gap>=0 else (-penalty*gap,0.5*penalty*gap*gap)

def laminate_abd(plies):
    # plies: dict E1,E2,G12,nu12,theta_deg,t
    total=sum(p['t'] for p in plies); z=-total/2; A=np.zeros((3,3));B=np.zeros((3,3));D=np.zeros((3,3))
    for p in plies:
        E1,E2,G,v=p['E1'],p['E2'],p['G12'],p['nu12']; v21=v*E2/E1; den=1-v*v21;Q=np.array([[E1/den,v*E2/den,0],[v*E2/den,E2/den,0],[0,0,G]])
        th=np.deg2rad(p.get('theta_deg',0));m=np.cos(th);n=np.sin(th);T=np.array([[m*m,n*n,2*m*n],[n*n,m*m,-2*m*n],[-m*n,m*n,m*m-n*n]])
        Qi=np.linalg.inv(T)@Q@np.linalg.inv(T).T; z2=z+p['t']; A+=Qi*(z2-z);B+=.5*Qi*(z2*z2-z*z);D+=(1/3)*Qi*(z2**3-z**3);z=z2
    return A,B,D

def richardson(Q1,Q2,Q3,r):
    ratio=(Q3-Q2)/(Q2-Q1)
    if ratio<=0: return {'observed_order':float('nan'),'extrapolated':float('nan')}
    p=np.log(ratio)/np.log(r); ext=Q1+(Q1-Q2)/(r**p-1); return {'observed_order':float(p),'extrapolated':float(ext)}


# ================= CELESTIAL DEPTH: FEA material / geometry / solve contracts =================
def _material(E,nu):
    E=float(E);nu=float(nu)
    if not np.isfinite([E,nu]).all() or E<=0 or not -1.0<nu<0.5: raise ValueError('finite E>0 and -1<nu<0.5 required')
    return E,nu

_elasticity_pre_celestial=elasticity_matrix
def elasticity_matrix(E,nu):
    E,nu=_material(E,nu);return _elasticity_pre_celestial(E,nu)

_tet4_B_pre_celestial=tet4_B
def tet4_B(X):
    X=np.asarray(X,float)
    if X.shape!=(4,3) or not np.all(np.isfinite(X)): raise ValueError('Tet4 coordinates must be finite 4x3')
    det=float(np.linalg.det(np.c_[X[1]-X[0],X[2]-X[0],X[3]-X[0]]))
    scale=max(1.0,float(np.max(np.linalg.norm(X-X[0],axis=1)))**3)
    if abs(det)<=100*np.finfo(float).eps*scale: raise ValueError('degenerate Tet4 volume')
    return _tet4_B_pre_celestial(X)

_solve_tet4_pre_celestial=solve_tet4
def solve_tet4(nodes,tets,E,nu,loads=None,fixed=None):
    X=np.asarray(nodes,float);T=np.asarray(tets,int);E,nu=_material(E,nu)
    if X.ndim!=2 or X.shape[1]!=3 or len(X)<4 or T.ndim!=2 or T.shape[1]!=4 or not np.all(np.isfinite(X)): raise ValueError('finite nodes Nx3 and Tet4 connectivity Mx4 required')
    if T.size and (np.min(T)<0 or np.max(T)>=len(X)): raise IndexError('tet connectivity out of range')
    nd=3*len(X)
    for d in (loads or {}):
        if int(d)!=d or not 0<=int(d)<nd: raise IndexError('load DOF out of range')
    for d in (fixed or []):
        if int(d)!=d or not 0<=int(d)<nd: raise IndexError('fixed DOF out of range')
    for tet in T: tet4_B(X[tet])
    r=_solve_tet4_pre_celestial(X,T,E,nu,loads,fixed)
    if not np.all(np.isfinite(r.u)) or not np.all(np.isfinite(r.reactions)) or not np.isfinite(r.residual_norm): raise FloatingPointError('NUMERICAL_BREAKDOWN: non-finite Tet4 solution')
    return r

_truss_pre_celestial=truss2d
def truss2d(nodes,elements,E,A,loads=None,fixed=None):
    X=np.asarray(nodes,float);E=float(E);A=float(A)
    if X.ndim!=2 or X.shape[1]<2 or len(X)<2 or not np.all(np.isfinite(X)) or E<=0 or A<=0 or not np.isfinite([E,A]).all(): raise ValueError('invalid truss geometry/material')
    for i,j in elements:
        if not 0<=int(i)<len(X) or not 0<=int(j)<len(X): raise IndexError('element node out of range')
        if np.linalg.norm(X[int(j),:2]-X[int(i),:2])<=np.finfo(float).eps: raise ValueError('zero-length truss element')
    r=_truss_pre_celestial(X,elements,E,A,loads,fixed)
    if not np.isfinite(r.residual_norm) or not np.isfinite(r.condition): raise FloatingPointError('NUMERICAL_BREAKDOWN: truss solve invalid')
    return r

_cst_pre_celestial=cst_stiffness
def cst_stiffness(X,E,nu,t=1.0,plane_stress=True):
    E,nu=_material(E,nu);t=float(t)
    if t<=0 or not np.isfinite(t): raise ValueError('thickness must be positive finite')
    return _cst_pre_celestial(X,E,nu,t,plane_stress)

_newmark_pre_celestial=newmark
def newmark(M,C,K,f,dt,n,u0=None,v0=None,beta=.25,gamma=.5):
    M=np.asarray(M,float);C=np.asarray(C,float);K=np.asarray(K,float);dt=float(dt);n=int(n);beta=float(beta);gamma=float(gamma)
    if M.ndim!=2 or M.shape[0]!=M.shape[1] or C.shape!=M.shape or K.shape!=M.shape or not all(np.all(np.isfinite(a)) for a in (M,C,K)): raise ValueError('M/C/K must be finite same-size square matrices')
    if dt<=0 or n<0 or beta<=0 or gamma<0 or not np.isfinite([dt,beta,gamma]).all(): raise ValueError('invalid Newmark dt/n/beta/gamma')
    if np.min(np.linalg.eigvalsh(.5*(M+M.T)))<=0: raise ValueError('mass matrix must be positive definite')
    out=_newmark_pre_celestial(M,C,K,f,dt,n,u0,v0,beta,gamma)
    if not all(np.all(np.isfinite(a)) for a in out): raise FloatingPointError('NUMERICAL_BREAKDOWN: Newmark returned NaN/Inf')
    return out

_modal_pre_celestial=modal
def modal(K,M,n_modes=6):
    K=np.asarray(K,float);M=np.asarray(M,float);n_modes=int(n_modes)
    if K.shape!=M.shape or K.ndim!=2 or K.shape[0]!=K.shape[1] or n_modes<1 or not np.all(np.isfinite(K)) or not np.all(np.isfinite(M)): raise ValueError('invalid modal matrices/request')
    if not np.allclose(K,K.T,rtol=1e-10,atol=1e-12) or not np.allclose(M,M.T,rtol=1e-10,atol=1e-12): raise ValueError('modal K/M must be symmetric')
    return _modal_pre_celestial(K,M,n_modes)

_buckling_pre_celestial=buckling
def buckling(K,Kg,n_modes=6):
    K=np.asarray(K,float);Kg=np.asarray(Kg,float);n_modes=int(n_modes)
    if K.shape!=Kg.shape or K.ndim!=2 or K.shape[0]!=K.shape[1] or n_modes<1 or not np.all(np.isfinite(K)) or not np.all(np.isfinite(Kg)): raise ValueError('invalid buckling matrices/request')
    return _buckling_pre_celestial(K,Kg,n_modes)

_thermal_pre_celestial=thermal_bar
def thermal_bar(length,n,k,A,q=0,T0=0,T1=1):
    length=float(length);n=int(n);k=float(k);A=float(A);q=float(q);T0=float(T0);T1=float(T1)
    if n<1 or min(length,k,A)<=0 or not np.isfinite([length,k,A,q,T0,T1]).all(): raise ValueError('invalid thermal-bar parameters')
    return _thermal_pre_celestial(length,n,k,A,q,T0,T1)

_j2_pre_celestial=j2_radial_return
def j2_radial_return(strain_inc,stress_old,ep_old,E,nu,sigy,H=0):
    de=np.asarray(strain_inc,float);s=np.asarray(stress_old,float);E,nu=_material(E,nu);ep_old=float(ep_old);sigy=float(sigy);H=float(H)
    if de.shape!=(6,) or s.shape!=(6,) or not np.all(np.isfinite(de)) or not np.all(np.isfinite(s)) or ep_old<0 or sigy<=0 or H<0 or not np.isfinite([ep_old,sigy,H]).all(): raise ValueError('invalid J2 state/material')
    return _j2_pre_celestial(de,s,ep_old,E,nu,sigy,H)

def penalty_contact(gap,penalty):
    gap=float(gap);penalty=float(penalty)
    if not np.isfinite([gap,penalty]).all() or penalty<=0: raise ValueError('positive finite penalty required')
    return (0.0,0.0) if gap>=0 else (-penalty*gap,0.5*penalty*gap*gap)

_laminate_pre_celestial=laminate_abd
def laminate_abd(plies):
    if not isinstance(plies,(list,tuple)) or not plies: raise ValueError('at least one ply required')
    for p in plies:
        for k in ('E1','E2','G12','nu12','t'):
            if k not in p or not np.isfinite(float(p[k])): raise ValueError(f'invalid/missing ply field {k}')
        if min(float(p['E1']),float(p['E2']),float(p['G12']),float(p['t']))<=0: raise ValueError('ply moduli/thickness must be positive')
        if abs(float(p['nu12']))>=1: raise ValueError('invalid ply Poisson ratio')
    return _laminate_pre_celestial(plies)

def richardson(Q1,Q2,Q3,r):
    Q1,Q2,Q3,r=map(float,(Q1,Q2,Q3,r))
    if not np.isfinite([Q1,Q2,Q3,r]).all() or r<=1: raise ValueError('finite results and refinement ratio r>1 required')
    den=Q2-Q1
    if abs(den)<=np.finfo(float).tiny:return {'observed_order':float('nan'),'extrapolated':float(Q1),'status':'INDETERMINATE_ZERO_DIFFERENCE'}
    ratio=(Q3-Q2)/den
    if ratio<=0:return {'observed_order':float('nan'),'extrapolated':float('nan'),'status':'NON_MONOTONIC'}
    p=np.log(ratio)/np.log(r);ext=Q1+(Q1-Q2)/(r**p-1);return {'observed_order':float(p),'extrapolated':float(ext),'status':'OK'}
