from __future__ import annotations
import numpy as np

def rmse(y,yh): y=np.asarray(y,float);yh=np.asarray(yh,float);return float(np.sqrt(np.mean((y-yh)**2)))
def mae(y,yh): y=np.asarray(y,float);yh=np.asarray(yh,float);return float(np.mean(np.abs(y-yh)))
def relative_error(x,ref,eps=1e-15): return float(abs(x-ref)/max(abs(ref),eps))
def observed_order(errors,hs):
    e=np.asarray(errors,float);h=np.asarray(hs,float);p=np.polyfit(np.log(h),np.log(e),1)[0];return float(p)
def richardson(Qfine,Qmedium,r,p): return float(Qfine+(Qfine-Qmedium)/(r**p-1))
def numerical_equivalent(x,ref,rtol=1e-8,atol=1e-10): return bool(np.allclose(x,ref,rtol=rtol,atol=atol))
def conservation_error(inp,out,eps=1e-15): return float(abs(inp-out)/max(abs(inp),eps))


# ================= CELESTIAL DEPTH: verification arithmetic =================
def _pair(y,yh):
    y=np.asarray(y,float); yh=np.asarray(yh,float)
    if y.shape!=yh.shape or y.size==0: raise ValueError('arrays must be non-empty and shape-compatible')
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(yh)): raise ValueError('arrays contain NaN/Inf')
    return y,yh

def rmse(y,yh):
    y,yh=_pair(y,yh); return float(np.sqrt(np.mean((y-yh)**2)))
def mae(y,yh):
    y,yh=_pair(y,yh); return float(np.mean(np.abs(y-yh)))
def relative_error(x,ref,eps=1e-15):
    x=float(x);ref=float(ref);eps=float(eps)
    if not np.isfinite([x,ref,eps]).all() or eps<=0: raise ValueError('finite x/ref and positive eps required')
    return float(abs(x-ref)/max(abs(ref),eps))
def observed_order(errors,hs):
    e=np.asarray(errors,float);h=np.asarray(hs,float)
    if e.ndim!=1 or h.ndim!=1 or len(e)!=len(h) or len(e)<2: raise ValueError('matching 1-D errors/hs with >=2 samples required')
    if np.any(~np.isfinite(e)) or np.any(~np.isfinite(h)) or np.any(e<=0) or np.any(h<=0): raise ValueError('errors and hs must be finite positive values')
    if np.unique(h).size<2: raise ValueError('hs must contain at least two distinct spacings')
    return float(np.polyfit(np.log(h),np.log(e),1)[0])
def richardson(Qfine,Qmedium,r,p):
    Qfine=float(Qfine);Qmedium=float(Qmedium);r=float(r);p=float(p)
    if not np.isfinite([Qfine,Qmedium,r,p]).all() or r<=0 or abs(r**p-1)<=np.finfo(float).eps: raise ValueError('invalid Richardson parameters')
    return float(Qfine+(Qfine-Qmedium)/(r**p-1))
def numerical_equivalent(x,ref,rtol=1e-8,atol=1e-10):
    x=np.asarray(x,float);ref=np.asarray(ref,float);rtol=float(rtol);atol=float(atol)
    if x.shape!=ref.shape or rtol<0 or atol<0: return False
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(ref)): return False
    return bool(np.allclose(x,ref,rtol=rtol,atol=atol))
def conservation_error(inp,out,eps=1e-15):
    inp=float(inp);out=float(out);eps=float(eps)
    if not np.isfinite([inp,out,eps]).all() or eps<=0: raise ValueError('finite values and positive eps required')
    return float(abs(inp-out)/max(abs(inp),eps))
