from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json,platform,sys,os,time
import numpy as np
from .provenance import sha256_file


def environment_fingerprint():
    payload={'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),'numpy':np.__version__,'cpu_count':os.cpu_count()}
    raw=json.dumps(payload,sort_keys=True).encode();payload['fingerprint_sha256']=hashlib.sha256(raw).hexdigest();return payload

@dataclass
class RunManifest:
    run_id:str; problem_hash:str; solver:str; solver_version:str; configuration_hash:str; status:str; mesh_hash:str=''; geometry_hash:str=''; material_hash:str=''; random_seed:int|None=None; command:str=''; results_hash:str=''; timestamp:float=0.0
    def __post_init__(self):
        if self.timestamp==0.0:self.timestamp=time.time()
    def to_dict(self):return asdict(self)

def hash_json(obj)->str:return hashlib.sha256(json.dumps(obj,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def build_release_evidence(paths):
    rows=[]
    for p in sorted(map(Path,paths),key=lambda x:str(x)):
        rows.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha256_file(p)})
    payload={'environment':environment_fingerprint(),'artifacts':rows};payload['manifest_sha256']=hash_json(payload);return payload
