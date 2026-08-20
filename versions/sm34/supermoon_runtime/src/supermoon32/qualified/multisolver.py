from __future__ import annotations
from dataclasses import dataclass,field
import numpy as np
from .verification import discrepancy
from ..core import InvalidInput

@dataclass
class NormalizedResult:
    field_name:str; units:str; value:object; source_tool:str; source_version:str=''; coordinates:object=None; time:float|None=None; uncertainty:object=None; mesh_reference:str=''; case_id:str=''

def compare_results(results:list[NormalizedResult],rtol_minor=.01,rtol_significant=.05,rtol_critical=.20):
    if len(results)<2:raise InvalidInput('at least two results required')
    base=np.asarray(results[0].value,float);rows=[]
    for r in results[1:]:
        if r.field_name!=results[0].field_name or r.units!=results[0].units:raise InvalidInput('result field/unit mismatch')
        v=np.asarray(r.value,float)
        if v.shape!=base.shape:raise InvalidInput('result shape mismatch')
        ae=float(np.max(np.abs(v-base)));den=max(float(np.max(np.abs(v))),float(np.max(np.abs(base))),1e-30);rel=ae/den
        cls='AGREEMENT' if rel<rtol_minor else 'MINOR_DISCREPANCY' if rel<rtol_significant else 'SIGNIFICANT_DISCREPANCY' if rel<rtol_critical else 'CRITICAL_DISCREPANCY'
        rows.append({'reference':results[0].source_tool,'candidate':r.source_tool,'max_absolute':ae,'max_relative':rel,'classification':cls})
    return rows
