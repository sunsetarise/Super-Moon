from __future__ import annotations
import numpy as np
from ..core import InvalidInput

def compare_precision(fn,input_array,dtypes=(np.float32,np.float64)):
    x=np.asarray(input_array)
    results={}
    for dt in dtypes:
        y=np.asarray(fn(x.astype(dt)))
        results[np.dtype(dt).name]=y
    ref=results[np.dtype(dtypes[-1]).name].astype(float);metrics={}
    for k,y in results.items():
        yf=y.astype(float);metrics[k]={'relative_l2':float(np.linalg.norm(yf-ref)/max(np.linalg.norm(ref),1e-30)),'max_absolute':float(np.max(np.abs(yf-ref)))}
    return {'results':results,'metrics':metrics,'reference_dtype':np.dtype(dtypes[-1]).name}
