from __future__ import annotations
import numpy as np

def aitken_fixed_point(G,x0,tol=1e-8,maxiter=100,omega0=.5):
    x=np.asarray(x0,float);omega=omega0;rprev=None;hist=[]
    for k in range(maxiter):
        gx=np.asarray(G(x),float);r=gx-x
        if rprev is not None:
            d=r-rprev; den=float(d@d)
            if den>1e-300: omega=float(np.clip(-omega*(rprev@d)/den,.05,1.5))
        xn=x+omega*r; hist.append(float(np.linalg.norm(r)))
        if hist[-1]<tol:return xn,{'converged':True,'iterations':k+1,'history':hist,'omega':omega}
        rprev=r;x=xn
    return x,{'converged':False,'iterations':maxiter,'history':hist,'omega':omega}

def conservative_scale(values,weights_src,weights_dst):
    v=np.asarray(values,float);ws=np.asarray(weights_src,float);wd=np.asarray(weights_dst,float); total=float(np.dot(v,ws)); mapped=np.full_like(wd,total/max(wd.sum(),1e-300)); return mapped

def nearest_transfer(src_xyz,src_val,dst_xyz):
    s=np.asarray(src_xyz,float);d=np.asarray(dst_xyz,float);v=np.asarray(src_val); idx=np.argmin(((d[:,None,:]-s[None,:,:])**2).sum(2),axis=1);return v[idx]

def fsi_partitioned(fluid,structure,x0,tol=1e-7,maxiter=50):
    def G(x): return structure(fluid(x))
    return aitken_fixed_point(G,x0,tol,maxiter)

def conjugate_interface(kf,ks,Tf_far,Ts_far,Lf,Ls):
    # exact 1-D two-material interface from flux continuity
    q=(Tf_far-Ts_far)/(Lf/kf+Ls/ks); Ti=Tf_far-q*Lf/kf; return {'interface_temperature':Ti,'heat_flux':q}


# ================= CELESTIAL DEPTH: coupling invariants / convergence =================
def aitken_fixed_point(G,x0,tol=1e-8,maxiter=100,omega0=.5):
    x=np.asarray(x0,float).copy();tol=float(tol);maxiter=int(maxiter);omega=float(omega0)
    if x.size==0 or not np.all(np.isfinite(x)): raise ValueError('finite non-empty x0 required')
    if tol<=0 or not np.isfinite(tol) or maxiter<1 or not np.isfinite(omega) or omega<=0: raise ValueError('positive tol/maxiter/omega0 required')
    rprev=None;hist=[]
    for k in range(maxiter):
        gx=np.asarray(G(x),float)
        if gx.shape!=x.shape or not np.all(np.isfinite(gx)): raise FloatingPointError('NUMERICAL_BREAKDOWN: coupling map returned invalid state')
        r=gx-x;rn=float(np.linalg.norm(r));hist.append(rn)
        if rn<tol:return x+omega*r,{'converged':True,'iterations':k+1,'history':hist,'omega':omega,'status':'CONVERGED'}
        if rprev is not None:
            d=r-rprev; den=float(d@d)
            if den>np.finfo(float).tiny:
                candidate=-omega*float(rprev@d)/den
                if np.isfinite(candidate): omega=float(np.clip(candidate,.05,1.5))
        xn=x+omega*r
        if not np.all(np.isfinite(xn)): raise FloatingPointError('NUMERICAL_BREAKDOWN: non-finite coupled iterate')
        rprev=r.copy();x=xn
    return x,{'converged':False,'iterations':maxiter,'history':hist,'omega':omega,'status':'NONCONVERGED'}

def conservative_scale(values,weights_src,weights_dst):
    v=np.asarray(values,float);ws=np.asarray(weights_src,float);wd=np.asarray(weights_dst,float)
    if v.ndim!=1 or ws.shape!=v.shape or wd.ndim!=1 or wd.size==0: raise ValueError('1-D values/source weights and non-empty destination weights required')
    if not np.all(np.isfinite(v)) or not np.all(np.isfinite(ws)) or not np.all(np.isfinite(wd)): raise ValueError('non-finite transfer data')
    denom=float(wd.sum())
    if abs(denom)<=np.finfo(float).tiny: raise ValueError('destination weights sum to zero')
    total=float(np.dot(v,ws)); mapped=np.full(wd.shape,total/denom,dtype=float)
    # Same constant conservative map, now checked rather than assumed.
    defect=abs(float(mapped@wd)-total)
    if defect>1e-12*max(1.0,abs(total)): raise FloatingPointError('NUMERICAL_BREAKDOWN: conservative map failed conservation check')
    return mapped

def nearest_transfer(src_xyz,src_val,dst_xyz):
    s=np.asarray(src_xyz,float);d=np.asarray(dst_xyz,float);v=np.asarray(src_val)
    if s.ndim!=2 or d.ndim!=2 or s.shape[1]!=d.shape[1] or len(s)!=len(v) or len(s)==0: raise ValueError('source/destination coordinate dimensions or values mismatch')
    if not np.all(np.isfinite(s)) or not np.all(np.isfinite(d)): raise ValueError('coordinates contain NaN/Inf')
    idx=np.argmin(((d[:,None,:]-s[None,:,:])**2).sum(2),axis=1);return v[idx]

def conjugate_interface(kf,ks,Tf_far,Ts_far,Lf,Ls):
    kf,ks,Lf,Ls,Tf_far,Ts_far=map(float,(kf,ks,Lf,Ls,Tf_far,Ts_far))
    if not np.isfinite([kf,ks,Lf,Ls,Tf_far,Ts_far]).all() or min(kf,ks,Lf,Ls)<=0: raise ValueError('positive finite conductivities/lengths and finite temperatures required')
    den=Lf/kf+Ls/ks;q=(Tf_far-Ts_far)/den;Ti=Tf_far-q*Lf/kf
    left=q-(Tf_far-Ti)*kf/Lf;right=q-(Ti-Ts_far)*ks/Ls
    return {'interface_temperature':Ti,'heat_flux':q,'flux_balance_error':float(max(abs(left),abs(right)))}
