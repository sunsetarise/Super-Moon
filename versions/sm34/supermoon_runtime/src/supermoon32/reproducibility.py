from __future__ import annotations
import hashlib,json,platform,sys,os
from pathlib import Path
import numpy as np

def sha256_bytes(b):return hashlib.sha256(b).hexdigest()
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()
def environment_fingerprint(seed=None):
    out={'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),'numpy':np.__version__,'cpu_count':os.cpu_count(),'seed':seed}
    try:import scipy;out['scipy']=scipy.__version__
    except Exception:out['scipy']=None
    return out
def deterministic_rng(seed):return np.random.default_rng(int(seed))
def manifest(root):
    root=Path(root);rows=[]
    for p in sorted(x for x in root.rglob('*') if x.is_file()):rows.append({'path':str(p.relative_to(root)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha256_file(p)})
    return rows
def verify_manifest(root,rows):
    root=Path(root);bad=[]
    for r in rows:
        p=root/r['path'];ok=p.exists() and p.stat().st_size==r['bytes'] and sha256_file(p)==r['sha256']
        if not ok:bad.append(r['path'])
    return {'passed':not bad,'verified':len(rows)-len(bad),'total':len(rows),'bad':bad}
