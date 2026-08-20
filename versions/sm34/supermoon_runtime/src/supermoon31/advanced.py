from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares
from scipy.integrate import solve_ivp

# ------------------------- CAD constraint numerics -------------------------
class ConstraintSystem:
    """Numerical parametric constraint system F(x)=0 with rank/DOF diagnostics."""
    def __init__(self,n_unknowns): self.n=n_unknowns; self.constraints=[]
    def add(self,fun,name=None): self.constraints.append((name or f'c{len(self.constraints)}',fun)); return self
    def residual(self,x): return np.concatenate([np.atleast_1d(f(np.asarray(x,float))).astype(float) for _,f in self.constraints])
    def solve(self,x0,xtol=1e-12,ftol=1e-12,gtol=1e-12):
        r=least_squares(self.residual,np.asarray(x0,float),xtol=xtol,ftol=ftol,gtol=gtol,max_nfev=5000)
        s=np.linalg.svd(r.jac,compute_uv=False); tol=max(r.jac.shape)*np.finfo(float).eps*(s[0] if len(s) else 1); rank=int(np.sum(s>tol)); m=r.jac.shape[0]
        return {'x':r.x,'success':bool(r.success),'cost':float(r.cost),'rank':rank,'dof':self.n-rank,'overconstrained':m>self.n and rank>=self.n,'singular_values':s,'message':r.message}

# ----------------------- Generic nonlinear solution -----------------------
def newton_solve(residual,jacobian,x0,tol=1e-10,maxiter=50,line_search=True):
    x=np.asarray(x0,float).copy(); hist=[]
    for k in range(maxiter):
        r=np.asarray(residual(x),float); rn=float(np.linalg.norm(r));hist.append(rn)
        if rn<tol:return x,{'converged':True,'iterations':k,'history':hist}
        J=np.asarray(jacobian(x),float); dx=np.linalg.solve(J,-r); alpha=1.0
        if line_search:
            base=rn
            while alpha>1e-6 and np.linalg.norm(residual(x+alpha*dx)) >= base*(1-1e-4*alpha): alpha*=.5
        x=x+alpha*dx
    return x,{'converged':False,'iterations':maxiter,'history':hist}

def continuation(load_steps,solve_at,x0):
    x=np.asarray(x0,float); path=[]
    for lam in load_steps:
        x,info=solve_at(lam,x);path.append({'lambda':float(lam),'x':x.copy(),'info':info})
        if not info.get('converged',False):break
    return path

# --------------------------- Beam / shell FEA -----------------------------
def euler_bernoulli_beam_stiffness(E,I,L):
    return E*I/L**3*np.array([[12,6*L,-12,6*L],[6*L,4*L*L,-6*L,2*L*L],[-12,-6*L,12,-6*L],[6*L,2*L*L,-6*L,4*L*L]],float)

def timoshenko_beam_stiffness(E,I,G,A,L,kappa=5/6):
    phi=12*E*I/(kappa*G*A*L*L); c=E*I/(L**3*(1+phi))
    return c*np.array([[12,6*L,-12,6*L],[6*L,(4+phi)*L*L,-6*L,(2-phi)*L*L],[-12,-6*L,12,-6*L],[6*L,(2-phi)*L*L,-6*L,(4+phi)*L*L]])

def mindlin_plate_q4_stiffness(X,E,nu,t,kappa=5/6):
    """4-node Mindlin plate, 3 dof/node [w,theta_x,theta_y], 2x2 integration."""
    X=np.asarray(X,float)[:,:2]
    Db=E*t**3/(12*(1-nu**2))*np.array([[1,nu,0],[nu,1,0],[0,0,(1-nu)/2]])
    G=E/(2*(1+nu)); Ds=kappa*G*t*np.eye(2); K=np.zeros((12,12)); gp=[-1/np.sqrt(3),1/np.sqrt(3)]
    for xi in gp:
      for eta in gp:
        N=.25*np.array([(1-xi)*(1-eta),(1+xi)*(1-eta),(1+xi)*(1+eta),(1-xi)*(1+eta)])
        dxi=.25*np.array([[-(1-eta),-(1-xi)],[(1-eta),-(1+xi)],[(1+eta),(1+xi)],[-(1+eta),(1-xi)]])
        J=dxi.T@X; det=np.linalg.det(J)
        if det<=0: raise ValueError('invalid Q4 plate Jacobian')
        dN=dxi@np.linalg.inv(J); Bb=np.zeros((3,12));Bs=np.zeros((2,12))
        for a in range(4):
            w,tx,ty=3*a,3*a+1,3*a+2; dx,dy=dN[a]
            Bb[:,[tx,ty]]=[[dx,0],[0,dy],[dy,dx]]
            Bs[:,[w,tx,ty]]=[[dx,N[a],0],[dy,0,N[a]]]
        K+=(Bb.T@Db@Bb+Bs.T@Ds@Bs)*det
    return K

# --------------------- Hyperelasticity / finite strain --------------------
def neo_hookean_first_piola(F,mu,lam):
    F=np.asarray(F,float);J=np.linalg.det(F)
    if J<=0:raise ValueError('non-positive deformation Jacobian')
    FinvT=np.linalg.inv(F).T; return mu*(F-FinvT)+lam*np.log(J)*FinvT

def green_lagrange(F):
    F=np.asarray(F,float);return .5*(F.T@F-np.eye(F.shape[0]))

def von_mises(stress6):
    s=np.asarray(stress6,float);m=s[:3].mean();d=s.copy();d[:3]-=m;return float(np.sqrt(1.5*(d[:3]@d[:3]+2*d[3:]@d[3:])))

# ----------------------------- Contact ------------------------------------
def augmented_contact(gap,lambda_n,penalty):
    lam=max(0.0,float(lambda_n)-penalty*float(gap)); traction=lam; active=lam>0; return {'lambda':lam,'traction':traction,'active':active}
def coulomb_limit(normal_force,mu): return abs(mu*normal_force)

# -------------------------- Fracture mechanics ----------------------------
def mode_I_K(sigma,a,Y=1.0): return Y*sigma*np.sqrt(np.pi*a)
def energy_release_rate(K,E,nu=0.0,plane_strain=False): return K*K*(1-nu*nu)/E if plane_strain else K*K/E
def phase_field_energy_1d(u,d,E,Gc,ell,dx):
    u=np.asarray(u,float);d=np.asarray(d,float);du=np.diff(u)/dx;dd=np.diff(d)/dx;dmid=.5*(d[:-1]+d[1:]);elastic=.5*E*(1-dmid)**2*du**2;fracture=Gc*(.5*dmid**2/ell+.5*ell*dd**2);return float(np.sum((elastic+fracture)*dx))

# -------------------------- CFD advanced pieces ---------------------------
def hllc_flux(UL,UR,gamma=1.4):
    UL=np.asarray(UL,float);UR=np.asarray(UR,float)
    def prim(U):
        r=U[0];u=U[1]/r;p=(gamma-1)*(U[2]-.5*r*u*u);a=np.sqrt(gamma*p/r);return r,u,p,a
    def fl(U):
        r,u,p,a=prim(U);return np.array([r*u,r*u*u+p,u*(U[2]+p)])
    rL,uL,pL,aL=prim(UL);rR,uR,pR,aR=prim(UR);SL=min(uL-aL,uR-aR);SR=max(uL+aL,uR+aR)
    SM=(pR-pL+rL*uL*(SL-uL)-rR*uR*(SR-uR))/(rL*(SL-uL)-rR*(SR-uR))
    FL,FR=fl(UL),fl(UR)
    if 0<=SL:return FL
    if SL<=0<=SM:
        rs=rL*(SL-uL)/(SL-SM);Es=((SL-uL)*UL[2]-pL*uL+pL*SM)/(SL-SM);Us=np.array([rs,rs*SM,Es]);return FL+SL*(Us-UL)
    if SM<=0<=SR:
        rs=rR*(SR-uR)/(SR-SM);Es=((SR-uR)*UR[2]-pR*uR+pR*SM)/(SR-SM);Us=np.array([rs,rs*SM,Es]);return FR+SR*(Us-UR)
    return FR

def vof_advect_1d(alpha,u,dt,dx):
    a=np.asarray(alpha,float);vel=float(u); flux=np.empty(len(a)+1);up=a if vel>=0 else np.roll(a,-1); flux[1:-1]=vel*(a[:-1] if vel>=0 else a[1:]);flux[0]=vel*a[0];flux[-1]=vel*a[-1];an=a-dt/dx*(flux[1:]-flux[:-1]);return np.clip(an,0,1)
def level_set_reinitialize(phi,dx,steps=20,dtau=None):
    p=np.asarray(phi,float).copy();p0=p.copy();dtau=dtau or .3*dx;S=p0/np.sqrt(p0*p0+dx*dx)
    for _ in range(steps):
        grad=np.gradient(p,dx);p-=dtau*S*(np.abs(grad)-1)
    return p

def arrhenius_rate(T,A,n,Ea,R=8.314462618): return A*T**n*np.exp(-Ea/(R*T))
def integrate_species(Y0,t_span,rate_matrix,rtol=1e-8,atol=1e-10):
    M=np.asarray(rate_matrix,float); sol=solve_ivp(lambda t,y:M@y,t_span,np.asarray(Y0,float),method='BDF',rtol=rtol,atol=atol);return sol

def ale_flux(F,U,mesh_velocity): return np.asarray(F,float)-np.asarray(U,float)*float(mesh_velocity)
def acoustic_fft(signal,dt):
    x=np.asarray(signal,float);f=np.fft.rfftfreq(len(x),dt);A=np.abs(np.fft.rfft(x-np.mean(x)));return f,A

def discrete_adjoint(dR_dU,dJ_dU,dR_da,dJ_da):
    lam=np.linalg.solve(np.asarray(dR_dU,float).T,np.asarray(dJ_dU,float));grad=np.asarray(dJ_da,float)-lam@np.asarray(dR_da,float);return lam,grad

# --------------------------- Reliability ----------------------------------
def form_linear(mean,cov,a,b):
    """Exact FORM result for linear limit state g=a^T x+b with Gaussian x."""
    m=np.asarray(mean,float);C=np.asarray(cov,float);a=np.asarray(a,float);mu_g=float(a@m+b);sig=float(np.sqrt(a@C@a));beta=mu_g/sig;from math import erf,sqrt;pf=.5*(1-erf(beta/sqrt(2)));return {'beta':beta,'pf':pf}


# ================= CELESTIAL DEPTH: advanced existing-method robustness =================
_ConstraintSystem_solve_pre_celestial=ConstraintSystem.solve
def _celestial_constraint_solve(self,x0,xtol=1e-12,ftol=1e-12,gtol=1e-12):
    x0=np.asarray(x0,float)
    if self.n<=0 or x0.shape!=(self.n,) or not self.constraints or not np.all(np.isfinite(x0)): raise ValueError('constraint system requires finite x0 matching n and at least one constraint')
    for z,name in ((xtol,'xtol'),(ftol,'ftol'),(gtol,'gtol')):
        if float(z)<=0 or not np.isfinite(float(z)): raise ValueError(f'{name} must be positive finite')
    out=_ConstraintSystem_solve_pre_celestial(self,x0,xtol,ftol,gtol)
    rr=np.asarray(self.residual(out['x']),float);out['residual_norm']=float(np.linalg.norm(rr));out['status']='CONVERGED' if out['success'] else 'NONCONVERGED'
    if not np.all(np.isfinite(out['x'])) or not np.all(np.isfinite(rr)): raise FloatingPointError('NUMERICAL_BREAKDOWN: invalid constraint result')
    return out
ConstraintSystem.solve=_celestial_constraint_solve

def newton_solve(residual,jacobian,x0,tol=1e-10,maxiter=50,line_search=True):
    x=np.asarray(x0,float).copy();tol=float(tol);maxiter=int(maxiter)
    if x.size==0 or not np.all(np.isfinite(x)) or tol<=0 or maxiter<1: raise ValueError('finite non-empty x0, tol>0, maxiter>=1 required')
    hist=[]
    for k in range(maxiter):
        r=np.asarray(residual(x),float)
        if r.ndim!=1 or not np.all(np.isfinite(r)): raise FloatingPointError('NUMERICAL_BREAKDOWN: invalid Newton residual')
        rn=float(np.linalg.norm(r));hist.append(rn)
        if rn<tol:return x,{'converged':True,'iterations':k,'history':hist,'status':'CONVERGED'}
        J=np.asarray(jacobian(x),float)
        if J.shape!=(len(r),len(x)) or not np.all(np.isfinite(J)): raise ValueError('Jacobian shape/values invalid')
        try:dx=np.linalg.solve(J,-r)
        except np.linalg.LinAlgError as e: raise np.linalg.LinAlgError('NUMERICAL_BREAKDOWN: singular Newton Jacobian') from e
        alpha=1.0
        if line_search:
            accepted=False
            while alpha>1e-8:
                trial=x+alpha*dx;rt=np.asarray(residual(trial),float)
                if np.all(np.isfinite(rt)) and np.linalg.norm(rt)<rn*(1-1e-4*alpha):accepted=True;break
                alpha*=.5
            if not accepted:return x,{'converged':False,'iterations':k+1,'history':hist,'status':'NONCONVERGED_LINE_SEARCH'}
        x=x+alpha*dx
        if not np.all(np.isfinite(x)): raise FloatingPointError('NUMERICAL_BREAKDOWN: non-finite Newton iterate')
    return x,{'converged':False,'iterations':maxiter,'history':hist,'status':'NONCONVERGED_MAXITER'}

_continuation_pre_celestial=continuation
def continuation(load_steps,solve_at,x0):
    ls=np.asarray(list(load_steps),float)
    if ls.ndim!=1 or ls.size==0 or not np.all(np.isfinite(ls)) or np.any(np.diff(ls)<0): raise ValueError('load_steps must be finite nondecreasing sequence')
    return _continuation_pre_celestial(ls,solve_at,x0)

def _positive(values,names):
    vals=np.asarray(values,float)
    if np.any(~np.isfinite(vals)) or np.any(vals<=0): raise ValueError('positive finite '+','.join(names)+' required')
    return vals

_eb_pre=euler_bernoulli_beam_stiffness
def euler_bernoulli_beam_stiffness(E,I,L): _positive([E,I,L],['E','I','L']);return _eb_pre(E,I,L)
_tim_pre=timoshenko_beam_stiffness
def timoshenko_beam_stiffness(E,I,G,A,L,kappa=5/6): _positive([E,I,G,A,L,kappa],['E','I','G','A','L','kappa']);return _tim_pre(E,I,G,A,L,kappa)
_mindlin_pre=mindlin_plate_q4_stiffness
def mindlin_plate_q4_stiffness(X,E,nu,t,kappa=5/6):
    _positive([E,t,kappa],['E','t','kappa']);nu=float(nu)
    if not -1<nu<.5:return (_ for _ in ()).throw(ValueError('invalid Poisson ratio'))
    return _mindlin_pre(X,E,nu,t,kappa)
_neo_pre=neo_hookean_first_piola
def neo_hookean_first_piola(F,mu,lam):
    F=np.asarray(F,float);_positive([mu],['mu'])
    if not np.isfinite(float(lam)) or F.ndim!=2 or F.shape[0]!=F.shape[1] or not np.all(np.isfinite(F)): raise ValueError('invalid deformation gradient/material')
    if np.linalg.det(F)<=np.finfo(float).tiny: raise ValueError('non-positive/degenerate deformation Jacobian')
    return _neo_pre(F,mu,lam)
_green_pre=green_lagrange
def green_lagrange(F):
    F=np.asarray(F,float)
    if F.ndim!=2 or F.shape[0]!=F.shape[1] or not np.all(np.isfinite(F)): raise ValueError('finite square F required')
    return _green_pre(F)
_von_pre=von_mises
def von_mises(stress6):
    s=np.asarray(stress6,float)
    if s.shape!=(6,) or not np.all(np.isfinite(s)): raise ValueError('finite 6-component stress required')
    return _von_pre(s)
def augmented_contact(gap,lambda_n,penalty):
    gap,lambda_n,penalty=map(float,(gap,lambda_n,penalty));_positive([penalty],['penalty'])
    if not np.isfinite([gap,lambda_n]).all() or lambda_n<0: raise ValueError('finite gap and lambda_n>=0 required')
    lam=max(0.0,lambda_n-penalty*gap);return {'lambda':lam,'traction':lam,'active':lam>0,'complementarity':float(abs(min(gap,0.0)*lam))}
def coulomb_limit(normal_force,mu):
    normal_force=float(normal_force);mu=float(mu)
    if not np.isfinite([normal_force,mu]).all() or mu<0: raise ValueError('finite force and mu>=0 required')
    return abs(mu*normal_force)
def mode_I_K(sigma,a,Y=1.0):
    sigma,a,Y=map(float,(sigma,a,Y));_positive([a],['a'])
    if not np.isfinite([sigma,Y]).all(): raise ValueError('finite sigma/Y required')
    return Y*sigma*np.sqrt(np.pi*a)
def energy_release_rate(K,E,nu=0.0,plane_strain=False):
    K,E,nu=map(float,(K,E,nu));_positive([E],['E'])
    if not np.isfinite([K,nu]).all() or (plane_strain and not -1<nu<.5): raise ValueError('invalid fracture parameters')
    return K*K*(1-nu*nu)/E if plane_strain else K*K/E
def phase_field_energy_1d(u,d,E,Gc,ell,dx):
    u=np.asarray(u,float);d=np.asarray(d,float);_positive([E,Gc,ell,dx],['E','Gc','ell','dx'])
    if u.ndim!=1 or d.shape!=u.shape or len(u)<2 or not np.all(np.isfinite(u)) or not np.all(np.isfinite(d)) or np.any((d<0)|(d>1)): raise ValueError('finite equal 1-D u/d with 0<=d<=1 required')
    du=np.diff(u)/dx;dd=np.diff(d)/dx;dmid=.5*(d[:-1]+d[1:]);elastic=.5*E*(1-dmid)**2*du**2;fracture=Gc*(.5*dmid**2/ell+.5*ell*dd**2);return float(np.sum((elastic+fracture)*dx))

_hllc_pre=hllc_flux
def hllc_flux(UL,UR,gamma=1.4):
    UL=np.asarray(UL,float);UR=np.asarray(UR,float);gamma=float(gamma)
    if UL.shape!=(3,) or UR.shape!=(3,) or gamma<=1 or not np.all(np.isfinite(UL)) or not np.all(np.isfinite(UR)): raise ValueError('finite 3-state vectors and gamma>1 required')
    for U in (UL,UR):
        r=U[0]
        if r<=0: raise FloatingPointError('INVALID_INPUT: HLLC non-positive density')
        u=U[1]/r;p=(gamma-1)*(U[2]-.5*r*u*u)
        if p<=0: raise FloatingPointError('INVALID_INPUT: HLLC non-positive pressure')
    out=_hllc_pre(UL,UR,gamma)
    if not np.all(np.isfinite(out)): raise FloatingPointError('NUMERICAL_BREAKDOWN: non-finite HLLC flux')
    return out

def vof_advect_1d(alpha,u,dt,dx):
    a=np.asarray(alpha,float);vel=float(u);dt=float(dt);dx=float(dx)
    if a.ndim!=1 or a.size<2 or not np.all(np.isfinite(a)) or np.any((a<0)|(a>1)) or not np.isfinite([vel,dt,dx]).all() or dt<0 or dx<=0: raise ValueError('invalid VOF state/step')
    courant=abs(vel)*dt/dx
    if courant>1+1e-12: raise ValueError('VOF explicit upwind CFL exceeds 1')
    flux=np.empty(len(a)+1);flux[1:-1]=vel*(a[:-1] if vel>=0 else a[1:]);flux[0]=vel*a[0];flux[-1]=vel*a[-1];an=a-dt/dx*(flux[1:]-flux[:-1]);return np.clip(an,0,1)
def level_set_reinitialize(phi,dx,steps=20,dtau=None):
    p=np.asarray(phi,float).copy();dx=float(dx);steps=int(steps)
    if p.ndim!=1 or p.size<3 or not np.all(np.isfinite(p)) or dx<=0 or steps<0 or not np.isfinite(dx): raise ValueError('invalid level-set state/grid')
    dtau=.3*dx if dtau is None else float(dtau)
    if dtau<=0 or not np.isfinite(dtau): raise ValueError('dtau must be positive finite')
    p0=p.copy();S=p0/np.sqrt(p0*p0+dx*dx)
    for _ in range(steps):
        grad=np.gradient(p,dx);p-=dtau*S*(np.abs(grad)-1)
        if not np.all(np.isfinite(p)): raise FloatingPointError('NUMERICAL_BREAKDOWN: level-set reinitialization diverged')
    return p
def arrhenius_rate(T,A,n,Ea,R=8.314462618):
    T,A,n,Ea,R=map(float,(T,A,n,Ea,R))
    if not np.isfinite([T,A,n,Ea,R]).all() or T<=0 or A<0 or R<=0: raise ValueError('invalid Arrhenius parameters')
    return A*T**n*np.exp(-Ea/(R*T))
def integrate_species(Y0,t_span,rate_matrix,rtol=1e-8,atol=1e-10):
    y=np.asarray(Y0,float);M=np.asarray(rate_matrix,float);rtol=float(rtol);atol=float(atol)
    if y.ndim!=1 or M.shape!=(len(y),len(y)) or not np.all(np.isfinite(y)) or not np.all(np.isfinite(M)) or rtol<=0 or atol<=0: raise ValueError('invalid species system/tolerances')
    if len(t_span)!=2 or not np.isfinite(t_span).all() or t_span[1]<=t_span[0]: raise ValueError('t_span must be finite increasing pair')
    sol=solve_ivp(lambda t,z:M@z,t_span,y,method='BDF',rtol=rtol,atol=atol)
    if not sol.success: return sol
    if not np.all(np.isfinite(sol.y)): raise FloatingPointError('NUMERICAL_BREAKDOWN: species integration returned NaN/Inf')
    return sol
def ale_flux(F,U,mesh_velocity):
    F=np.asarray(F,float);U=np.asarray(U,float);mv=float(mesh_velocity)
    if F.shape!=U.shape or not np.all(np.isfinite(F)) or not np.all(np.isfinite(U)) or not np.isfinite(mv): raise ValueError('finite shape-compatible F/U and velocity required')
    return F-U*mv
def acoustic_fft(signal,dt):
    x=np.asarray(signal,float);dt=float(dt)
    if x.ndim!=1 or x.size<2 or not np.all(np.isfinite(x)) or dt<=0 or not np.isfinite(dt): raise ValueError('finite signal length>=2 and dt>0 required')
    f=np.fft.rfftfreq(len(x),dt);A=np.abs(np.fft.rfft(x-np.mean(x)));return f,A
def discrete_adjoint(dR_dU,dJ_dU,dR_da,dJ_da):
    A=np.asarray(dR_dU,float);j=np.asarray(dJ_dU,float);B=np.asarray(dR_da,float);ja=np.asarray(dJ_da,float)
    if A.ndim!=2 or A.shape[0]!=A.shape[1] or j.shape!=(A.shape[0],) or B.shape[0]!=A.shape[0] or not all(np.all(np.isfinite(z)) for z in (A,j,B,ja)): raise ValueError('invalid discrete-adjoint dimensions/data')
    try:lam=np.linalg.solve(A.T,j)
    except np.linalg.LinAlgError as e: raise np.linalg.LinAlgError('NUMERICAL_BREAKDOWN: singular adjoint operator') from e
    grad=ja-lam@B
    if not np.all(np.isfinite(grad)): raise FloatingPointError('NUMERICAL_BREAKDOWN: non-finite adjoint gradient')
    return lam,grad
def form_linear(mean,cov,a,b):
    m=np.asarray(mean,float);C=np.asarray(cov,float);a=np.asarray(a,float);b=float(b)
    if m.ndim!=1 or a.shape!=m.shape or C.shape!=(len(m),len(m)) or not all(np.all(np.isfinite(z)) for z in (m,C,a)) or not np.isfinite(b): raise ValueError('invalid FORM dimensions/data')
    C=.5*(C+C.T);eig=np.linalg.eigvalsh(C)
    if np.min(eig)<-1e-12*max(1.0,float(np.max(abs(eig)))): raise ValueError('covariance matrix is not positive semidefinite')
    mu_g=float(a@m+b);var=float(a@C@a)
    if var<=np.finfo(float).tiny: raise ValueError('limit-state variance is zero')
    sig=float(np.sqrt(var));beta=mu_g/sig;from math import erf,sqrt;pf=.5*(1-erf(beta/sqrt(2)));return {'beta':beta,'pf':pf,'sigma_g':sig,'mean_g':mu_g}
