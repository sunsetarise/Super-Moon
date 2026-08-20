from __future__ import annotations
import numpy as np
from .cad import CadKernel,ShapeRecord
from .optimization import optimize

def parametric_wing(span,root_chord,tip_chord,thickness=0.12):
    k=CadKernel(); half=span/2
    # robust engineering reference wing as tapered solid; keeps CAD/STEP path executable.
    import cadquery as cq
    wp=cq.Workplane('YZ').workplane(offset=0).rect(root_chord,thickness*root_chord).workplane(offset=half).rect(tip_chord,thickness*tip_chord).loft(combine=True)
    return ShapeRecord(wp,'wing.reference',{'span':span,'root_chord':root_chord,'tip_chord':tip_chord,'thickness_ratio':thickness,'fidelity':'reference solid loft'})
def aerodynamic_surrogate(span,area,cd0=.02,e=.82,rho=1.225,V=70,W=1e5):
    AR=span*span/area;q=.5*rho*V*V;CL=W/(q*area);CD=cd0+CL*CL/(np.pi*e*AR);return {'CL':CL,'CD':CD,'drag':q*area*CD,'AR':AR,'fidelity':'SURROGATE'}
def optimize_wing(W=1e5,V=70,rho=1.225):
    def obj(x):
        span,area=x;a=aerodynamic_surrogate(span,area,rho=rho,V=V,W=W);return a['drag']+.02*area*1000
    r=optimize(obj,[30,100],bounds=[(10,60),(20,250)]);return r

def conservative_load_check(source_forces,target_forces,tol=1e-8):
    a=np.asarray(source_forces,float).sum(axis=0);b=np.asarray(target_forces,float).sum(axis=0);err=float(np.linalg.norm(a-b)/max(np.linalg.norm(a),1e-300));return {'pass':err<tol,'relative_force_error':err}


# ================= CELESTIAL DEPTH: existing aircraft-reference domain checks =================
_parametric_wing_pre_celestial=parametric_wing

def parametric_wing(span,root_chord,tip_chord,thickness=0.12):
    vals=np.asarray([span,root_chord,tip_chord,thickness],float)
    if np.any(~np.isfinite(vals)) or min(span,root_chord,tip_chord)<=0 or not 0<thickness<1: raise ValueError('positive finite dimensions and 0<thickness<1 required')
    return _parametric_wing_pre_celestial(float(span),float(root_chord),float(tip_chord),float(thickness))

def aerodynamic_surrogate(span,area,cd0=.02,e=.82,rho=1.225,V=70,W=1e5):
    span,area,cd0,e,rho,V,W=map(float,(span,area,cd0,e,rho,V,W))
    if not np.isfinite([span,area,cd0,e,rho,V,W]).all() or span<=0 or area<=0 or e<=0 or rho<=0 or V<=0 or W<0 or cd0<0: raise ValueError('invalid aerodynamic surrogate domain')
    AR=span*span/area;q=.5*rho*V*V;CL=W/(q*area);CD=cd0+CL*CL/(np.pi*e*AR);return {'CL':CL,'CD':CD,'drag':q*area*CD,'AR':AR,'dynamic_pressure':q,'fidelity':'SURROGATE'}

def optimize_wing(W=1e5,V=70,rho=1.225):
    W,V,rho=map(float,(W,V,rho))
    if not np.isfinite([W,V,rho]).all() or W<0 or V<=0 or rho<=0: raise ValueError('invalid wing optimization operating point')
    def obj(x):
        span,area=x;a=aerodynamic_surrogate(span,area,rho=rho,V=V,W=W);return a['drag']+.02*area*1000
    return optimize(obj,[30,100],bounds=[(10,60),(20,250)])

def conservative_load_check(source_forces,target_forces,tol=1e-8):
    s=np.asarray(source_forces,float);t=np.asarray(target_forces,float);tol=float(tol)
    if s.ndim!=2 or t.ndim!=2 or s.shape[1]!=t.shape[1] or s.size==0 or t.size==0 or not np.all(np.isfinite(s)) or not np.all(np.isfinite(t)): raise ValueError('finite non-empty force arrays with equal vector dimension required')
    if tol<0 or not np.isfinite(tol): raise ValueError('tol must be finite non-negative')
    a=s.sum(axis=0);b=t.sum(axis=0);abs_err=float(np.linalg.norm(a-b));err=abs_err/max(float(np.linalg.norm(a)),np.finfo(float).tiny);return {'pass':err<=tol,'relative_force_error':err,'absolute_force_error':abs_err,'source_resultant':a,'target_resultant':b}
