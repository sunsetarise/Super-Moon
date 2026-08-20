from __future__ import annotations
from pathlib import Path
import json,hashlib,platform,sys
import numpy as np
from .core import environment_manifest,sha256_file

def result_manifest(inputs,results,solver,tolerance,hardware=None):
    blob=json.dumps(inputs,sort_keys=True,default=str).encode();rblob=json.dumps(results,sort_keys=True,default=str).encode();return {'input_hash':hashlib.sha256(blob).hexdigest(),'result_hash':hashlib.sha256(rblob).hexdigest(),'hardware':hardware or platform.platform(),'solver':solver,'tolerance':tolerance,'python':sys.version}
def numerical_equivalence(x,ref,rtol=1e-8,atol=1e-10):
    x=np.asarray(x);ref=np.asarray(ref);err=float(np.max(np.abs(x-ref)/np.maximum(np.abs(ref),atol)));return {'pass':bool(np.allclose(x,ref,rtol=rtol,atol=atol)),'max_scaled_error':err,'rtol':rtol,'atol':atol}
def write_reproduction_pack(path):
    p=Path(path);p.mkdir(parents=True,exist_ok=True);(p/'environment.json').write_text(json.dumps(environment_manifest(),indent=2));(p/'README.txt').write_text('SUPER MOON 31 reproduction pack. Run pytest and canonical benchmarks in a clean environment.\n');return p


# ================= CELESTIAL DEPTH: canonical provenance =================
def _canonical(obj):
    if isinstance(obj,np.ndarray):
        a=np.asarray(obj)
        return {'__ndarray__':a.tolist(),'dtype':str(a.dtype),'shape':list(a.shape)}
    if isinstance(obj,np.generic): return obj.item()
    if isinstance(obj,dict): return {str(k):_canonical(obj[k]) for k in sorted(obj,key=lambda z:str(z))}
    if isinstance(obj,(list,tuple)): return [_canonical(v) for v in obj]
    if isinstance(obj,(str,int,bool)) or obj is None: return obj
    if isinstance(obj,float):
        if not np.isfinite(obj): raise ValueError('non-finite value cannot enter a reproducibility manifest')
        return obj
    return str(obj)

def _canonical_bytes(obj):
    return json.dumps(_canonical(obj),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def result_manifest(inputs,results,solver,tolerance,hardware=None):
    ib=_canonical_bytes(inputs); rb=_canonical_bytes(results)
    return {'input_hash':hashlib.sha256(ib).hexdigest(),'result_hash':hashlib.sha256(rb).hexdigest(),'hardware':hardware or platform.platform(),'solver':str(solver),'tolerance':_canonical(tolerance),'python':sys.version,'canonicalization':'SM31_CELESTIAL_JSON_V1'}

def numerical_equivalence(x,ref,rtol=1e-8,atol=1e-10):
    x=np.asarray(x,float);ref=np.asarray(ref,float);rtol=float(rtol);atol=float(atol)
    if x.shape!=ref.shape: return {'pass':False,'max_scaled_error':float('inf'),'rtol':rtol,'atol':atol,'reason':'shape_mismatch'}
    if rtol<0 or atol<0: raise ValueError('rtol/atol must be non-negative')
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(ref)): return {'pass':False,'max_scaled_error':float('inf'),'rtol':rtol,'atol':atol,'reason':'nonfinite'}
    scale=np.maximum(np.maximum(np.abs(ref)*rtol,atol),np.finfo(float).tiny)
    err=float(np.max(np.abs(x-ref)/scale)) if x.size else 0.0
    return {'pass':bool(np.allclose(x,ref,rtol=rtol,atol=atol)),'max_scaled_error':err,'rtol':rtol,'atol':atol,'reason':'ok'}

def write_reproduction_pack(path):
    p=Path(path);p.mkdir(parents=True,exist_ok=True)
    env=environment_manifest(); env_text=json.dumps(env,indent=2,sort_keys=True)
    (p/'environment.json').write_text(env_text,encoding='utf-8')
    (p/'environment.sha256').write_text(hashlib.sha256(env_text.encode()).hexdigest()+'\n',encoding='utf-8')
    (p/'README.txt').write_text('SUPER MOON 31 reproduction pack. Run pytest and canonical benchmarks in a clean environment. Compare numerical outputs with declared tolerances; backend presence is not qualification.\n',encoding='utf-8')
    return p
