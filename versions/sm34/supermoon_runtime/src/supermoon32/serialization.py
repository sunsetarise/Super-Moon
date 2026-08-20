from __future__ import annotations
import json,hashlib
from pathlib import Path
import numpy as np
from .core import InvalidInput
SCHEMA='SM32_STATE_V1'
def save_state(path,arrays,metadata=None):
    path=Path(path);meta={'schema':SCHEMA,'metadata':metadata or {},'arrays':{k:{'shape':list(np.asarray(v).shape),'dtype':str(np.asarray(v).dtype)} for k,v in arrays.items()}};payload=json.dumps(meta,sort_keys=True).encode();meta['metadata_sha256']=hashlib.sha256(payload).hexdigest();np.savez_compressed(path,__meta__=np.array(json.dumps(meta)),**arrays);return meta
def load_state(path):
    z=np.load(path,allow_pickle=False);meta=json.loads(str(z['__meta__']));
    if meta.get('schema')!=SCHEMA:raise InvalidInput('unsupported state schema')
    arrays={k:z[k] for k in z.files if k!='__meta__'}
    for k,spec in meta['arrays'].items():
        if k not in arrays or list(arrays[k].shape)!=spec['shape'] or str(arrays[k].dtype)!=spec['dtype']:raise InvalidInput('state array schema mismatch')
    return arrays,meta
