from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import hashlib, json, math, os, platform, sys, time
import numpy as np

class CapabilityLevel(str, Enum):
    L0='L0_SPECIFICATION'; L1='L1_EXPERIMENTAL'; L2='L2_UNIT_VERIFIED'; L3='L3_BENCHMARK_VERIFIED'; L4='L4_INDEPENDENTLY_REPRODUCED'; L5='L5_EXPERIMENTALLY_VALIDATED'; L6='L6_EXTERNAL_ACCEPTANCE_ONLY'
class Status(str, Enum):
    IMPLEMENTED='IMPLEMENTED'; EXPERIMENTAL='EXPERIMENTAL'; REFERENCE='REFERENCE'; SURROGATE='SURROGATE'; VALIDATION_PENDING='VALIDATION_PENDING'; HARDWARE_UNAVAILABLE='HARDWARE_UNAVAILABLE'; CERTIFICATION_SUPPORT_ONLY='CERTIFICATION_SUPPORT_ONLY'; NOT_IMPLEMENTED='NOT_IMPLEMENTED'

def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha256_file(path:str|Path, chunk=1<<20)->str:
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(chunk),b''): h.update(b)
    return h.hexdigest()

def stable_json(obj)->str: return json.dumps(obj, sort_keys=True, separators=(',',':'), default=str)

@dataclass(frozen=True)
class Provenance:
    code_hash:str='unknown'; geometry_hash:str=''; mesh_hash:str=''; material_hash:str=''; configuration_hash:str=''; solver:str=''; solver_version:str=''; hardware:str=platform.platform(); timestamp:float=0.0
    def finalized(self):
        return Provenance(**{**asdict(self),'timestamp':self.timestamp or time.time()})
    def digest(self): return sha256_bytes(stable_json(asdict(self.finalized())).encode())

# SI dimensional vector: kg,m,s,K,A,mol,cd
DIMS=('kg','m','s','K','A','mol','cd')
@dataclass(frozen=True)
class Quantity:
    value:float
    dim:tuple[int,...]=(0,0,0,0,0,0,0)
    def _check(self,o):
        if not isinstance(o,Quantity) or self.dim!=o.dim: raise ValueError(f'dimension mismatch {self.dim} vs {getattr(o,"dim",None)}')
    def __add__(self,o): self._check(o); return Quantity(self.value+o.value,self.dim)
    def __sub__(self,o): self._check(o); return Quantity(self.value-o.value,self.dim)
    def __mul__(self,o):
        if isinstance(o,Quantity): return Quantity(self.value*o.value,tuple(a+b for a,b in zip(self.dim,o.dim)))
        return Quantity(self.value*o,self.dim)
    __rmul__=__mul__
    def __truediv__(self,o):
        if isinstance(o,Quantity): return Quantity(self.value/o.value,tuple(a-b for a,b in zip(self.dim,o.dim)))
        return Quantity(self.value/o,self.dim)

UNIT={
 '1':Quantity(1), 'm':Quantity(1,(0,1,0,0,0,0,0)), 'mm':Quantity(1e-3,(0,1,0,0,0,0,0)),
 'kg':Quantity(1,(1,0,0,0,0,0,0)), 's':Quantity(1,(0,0,1,0,0,0,0)), 'K':Quantity(1,(0,0,0,1,0,0,0)),
 'N':Quantity(1,(1,1,-2,0,0,0,0)), 'Pa':Quantity(1,(1,-1,-2,0,0,0,0)), 'J':Quantity(1,(1,2,-2,0,0,0,0)), 'W':Quantity(1,(1,2,-3,0,0,0,0))}

def convergence(residual, r0=None, atol=1e-10, rtol=1e-8):
    r=float(abs(residual)); base=float(abs(r0 if r0 is not None else residual)); return r <= max(atol,rtol*base)

def condition_estimate(A): return float(np.linalg.cond(np.asarray(A,float)))
def central_difference(f,x,h=1e-6):
    x=np.asarray(x,float); g=np.empty_like(x)
    for i in range(x.size):
        d=np.zeros_like(x); d[i]=h; g[i]=(f(x+d)-f(x-d))/(2*h)
    return g

def directional_derivative_check(f, grad, x, d=None, eps=(1e-2,1e-3,1e-4,1e-5,1e-6)):
    x=np.asarray(x,float); d=np.ones_like(x) if d is None else np.asarray(d,float); d=d/max(np.linalg.norm(d),1e-300)
    target=float(np.dot(np.asarray(grad(x),float),d)); vals=[]
    for e in eps: vals.append((e, float((f(x+e*d)-f(x))/e), target))
    return vals

def environment_manifest():
    out={'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor()}
    for mod in ['numpy','scipy','cadquery','OCP','numba','mpi4py','petsc4py','slepc4py','cupy','triton']:
        try:
            m=__import__(mod); out[mod]=getattr(m,'__version__','available')
        except Exception: out[mod]=None
    return out


# ================= CELESTIAL DEPTH: core numerical contracts =================
# Same public capabilities; deeper finite-domain, tolerance, conditioning and status semantics.
class Status(str, Enum):
    IMPLEMENTED='IMPLEMENTED'; EXPERIMENTAL='EXPERIMENTAL'; REFERENCE='REFERENCE'; SURROGATE='SURROGATE'; VALIDATION_PENDING='VALIDATION_PENDING'; HARDWARE_UNAVAILABLE='HARDWARE_UNAVAILABLE'; CERTIFICATION_SUPPORT_ONLY='CERTIFICATION_SUPPORT_ONLY'; NOT_IMPLEMENTED='NOT_IMPLEMENTED'
    INVALID_INPUT='INVALID_INPUT'; NOT_APPLICABLE='NOT_APPLICABLE'; NONCONVERGED='NONCONVERGED'; NUMERICAL_BREAKDOWN='NUMERICAL_BREAKDOWN'; UNAVAILABLE_BACKEND='UNAVAILABLE_BACKEND'; UNQUALIFIED='UNQUALIFIED'

def _finite_array(x,name='value'):
    a=np.asarray(x,float)
    if not np.all(np.isfinite(a)): raise ValueError(f'{name} contains NaN/Inf')
    return a

def _finite_scalar(x,name='value'):
    x=float(x)
    if not math.isfinite(x): raise ValueError(f'{name} must be finite')
    return x

def convergence(residual, r0=None, atol=1e-10, rtol=1e-8):
    r=abs(_finite_scalar(residual,'residual'))
    base=r if r0 is None else abs(_finite_scalar(r0,'r0'))
    atol=_finite_scalar(atol,'atol'); rtol=_finite_scalar(rtol,'rtol')
    if atol<0 or rtol<0: raise ValueError('atol and rtol must be non-negative')
    return r <= max(atol,rtol*base)

def condition_estimate(A):
    a=_finite_array(A,'A')
    if a.ndim!=2 or min(a.shape)==0: raise ValueError('A must be a non-empty 2-D matrix')
    c=float(np.linalg.cond(a))
    return c

def central_difference(f,x,h=1e-6):
    x=_finite_array(x,'x')
    h=_finite_scalar(h,'h')
    if h<=0: raise ValueError('h must be positive')
    g=np.empty_like(x)
    for i in range(x.size):
        # Scale the same central-difference method to the coordinate magnitude to avoid
        # a dimensionally tiny perturbation on large coordinates.
        scale=max(1.0,abs(float(x.flat[i])))
        global_scale=max(1.0,float(np.linalg.norm(x,ord=np.inf)))
        # Keep the central-difference perturbation above the floating-point resolution
        # of the full objective scale. This remains the same second-order stencil.
        hi=max(h*scale, np.cbrt(np.finfo(float).eps)*global_scale)
        d=np.zeros_like(x); d.flat[i]=hi
        fp=_finite_scalar(f(x+d),'f(x+h)'); fm=_finite_scalar(f(x-d),'f(x-h)')
        g.flat[i]=(fp-fm)/(2*hi)
    return g

def directional_derivative_check(f, grad, x, d=None, eps=(1e-2,1e-3,1e-4,1e-5,1e-6)):
    x=_finite_array(x,'x'); d=np.ones_like(x) if d is None else _finite_array(d,'d')
    if d.shape!=x.shape: raise ValueError('d shape must match x')
    dn=float(np.linalg.norm(d))
    if dn<=np.finfo(float).tiny: raise ValueError('direction vector must be non-zero')
    d=d/dn
    gv=_finite_array(grad(x),'grad(x)')
    if gv.shape!=x.shape: raise ValueError('gradient shape must match x')
    target=float(np.dot(gv.ravel(),d.ravel())); vals=[]
    for e in eps:
        e=_finite_scalar(e,'epsilon')
        if e<=0: raise ValueError('all epsilon values must be positive')
        fp=_finite_scalar(f(x+e*d),'f(x+eps*d)'); f0=_finite_scalar(f(x),'f(x)')
        vals.append((e,float((fp-f0)/e),target))
    return vals
