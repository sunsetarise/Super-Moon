from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable
import math, time
import numpy as np

class SM32Error(Exception):
    """Base error for SUPER MOON 32."""
class InvalidInput(SM32Error):
    """InvalidInput error."""
class DimensionMismatch(SM32Error):
    """DimensionMismatch error."""
class NonPhysicalState(SM32Error):
    """NonPhysicalState error."""
class DegenerateGeometry(SM32Error):
    """DegenerateGeometry error."""
class SingularSystem(SM32Error):
    """SingularSystem error."""
class IllConditionedSystem(SM32Error):
    """IllConditionedSystem error."""
class ConvergenceFailure(SM32Error):
    """ConvergenceFailure error."""
class CFLViolation(SM32Error):
    """CFLViolation error."""
class InvariantViolation(SM32Error):
    """InvariantViolation error."""
class BackendUnavailable(SM32Error):
    """BackendUnavailable error."""
class NumericalOverflow(SM32Error):
    """NumericalOverflow error."""

class Determinism(str, Enum):
    BITWISE='BITWISE_DETERMINISTIC'; NUMERICAL='NUMERICALLY_DETERMINISTIC'; BOUNDED='NONDETERMINISTIC_BOUNDED'

@dataclass(frozen=True)
class TolerancePolicy:
    atol: float=1e-12; rtol: float=1e-9; geometry: float=1e-10; solver: float=1e-10; physical_floor: float=1e-12
    def close(self,a,b,scale=1.0): return abs(float(a)-float(b)) <= self.atol*max(1.0,float(scale)) + self.rtol*max(abs(float(a)),abs(float(b)))
DEFAULT_TOLERANCE=TolerancePolicy()

@dataclass
class SolverResult:
    solution: Any
    converged: bool
    iterations: int=0
    residual_norm: float=math.inf
    termination_reason: str=''
    runtime: float=0.0
    diagnostics: dict[str,Any]=field(default_factory=dict)
    history: list[float]=field(default_factory=list)
    status: str='OK'

@dataclass
class ValidationRecord:
    algorithm: str; case: str; expected: Any; actual: Any; error: Any; tolerance: Any; passed: bool; metadata: dict[str,Any]=field(default_factory=dict)


def finite_array(x,name='array',ndim=None):
    a=np.asarray(x,float)
    if ndim is not None and a.ndim!=ndim: raise DimensionMismatch(f'{name} must have ndim={ndim}, got {a.ndim}')
    if a.size==0: raise InvalidInput(f'{name} must be non-empty')
    if not np.all(np.isfinite(a)): raise InvalidInput(f'{name} contains NaN/Inf')
    return a

def finite_scalar(x,name='value'):
    try:v=float(x)
    except Exception as e: raise InvalidInput(f'{name} must be numeric') from e
    if not math.isfinite(v): raise InvalidInput(f'{name} must be finite')
    return v

def kahan_sum(values: Iterable[float])->float:
    s=0.0;c=0.0
    for x in values:
        y=float(x)-c;t=s+y;c=(t-s)-y;s=t
    return s

def stable_norm(x)->float:
    a=finite_array(x,'x').ravel(); m=float(np.max(np.abs(a)))
    if m==0:return 0.0
    return m*math.sqrt(float(np.dot(a/m,a/m)))

def safe_normalize(x,tol=DEFAULT_TOLERANCE):
    a=finite_array(x,'x'); n=stable_norm(a)
    if n <= tol.geometry*max(1.0,float(np.max(np.abs(a)))): raise DegenerateGeometry('cannot normalize near-zero vector')
    return a/n

def stable_polyval(coefficients,x):
    c=finite_array(coefficients,'coefficients',1); xv=finite_scalar(x,'x'); y=0.0
    for a in c:y=y*xv+float(a)
    if not math.isfinite(y): raise NumericalOverflow('polynomial evaluation overflow')
    return y

def scale_aware_tolerance(*values,base=None):
    base=np.finfo(float).eps if base is None else float(base); scale=max([1.0]+[abs(float(v)) for v in values]); return base*scale

def check_invariants(**checks):
    failed=[k for k,v in checks.items() if not bool(v)]
    if failed: raise InvariantViolation('failed invariants: '+', '.join(failed))
    return True

def timed_call(fn,*args,**kwargs):
    t=time.perf_counter(); out=fn(*args,**kwargs); return out,time.perf_counter()-t
