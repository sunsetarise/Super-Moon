from __future__ import annotations
import json,math
import numpy as np
from .core import ValidationRecord

def error_norms(actual,expected):
    a=np.asarray(actual,float);e=np.asarray(expected,float);d=np.abs(a-e);return {'L1':float(np.mean(d)),'L2':float(np.sqrt(np.mean(d*d))),'Linf':float(np.max(d))}
def observed_order(e_h,e_h2,ratio=2.):return float(np.log(e_h/e_h2)/np.log(ratio))
def conservation(initial,final,eps=1e-30):
    i=np.asarray(initial,float);f=np.asarray(final,float);ae=np.abs(f-i);re=ae/np.maximum(np.abs(i),eps);return {'absolute':ae.tolist(),'relative':re.tolist(),'max_absolute':float(ae.max()),'max_relative':float(re.max())}
def validate_close(algorithm,case,actual,expected,atol=1e-10,rtol=1e-8,metadata=None):
    a=np.asarray(actual,float);e=np.asarray(expected,float);err=error_norms(a,e);passed=bool(np.allclose(a,e,atol=atol,rtol=rtol));return ValidationRecord(algorithm,case,np.asarray(expected).tolist(),np.asarray(actual).tolist(),err,{'atol':atol,'rtol':rtol},passed,metadata or {})
def to_json(records):
    return json.dumps([r.__dict__ for r in records],indent=2,default=lambda o:o.tolist() if hasattr(o,'tolist') else str(o))
