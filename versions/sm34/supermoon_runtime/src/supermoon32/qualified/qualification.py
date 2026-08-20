from __future__ import annotations
from dataclasses import dataclass,field
from .enums import ClaimLevel
from ..core import InvalidInput

@dataclass
class QualificationState:
    capability_id:str; level:ClaimLevel; code_version:str; tool_version:str=''; hardware_fingerprint:str=''; regime:str=''; evidence_ids:list[str]=field(default_factory=list); valid:bool=True; invalidation_reasons:list[str]=field(default_factory=list)
    def invalidate(self,reason):self.valid=False;self.invalidation_reasons.append(str(reason));return self
    def downgrade(self,new_level:ClaimLevel,reason):
        if new_level>self.level:raise InvalidInput('downgrade target cannot exceed current level')
        self.level=new_level;self.invalidation_reasons.append(str(reason));return self

def change_requires_requalification(state:QualificationState,code_version=None,tool_version=None,hardware_fingerprint=None,regime=None):
    reasons=[]
    for name,new,old in [('code_version',code_version,state.code_version),('tool_version',tool_version,state.tool_version),('hardware_fingerprint',hardware_fingerprint,state.hardware_fingerprint),('regime',regime,state.regime)]:
        if new is not None and new!=old:reasons.append(name)
    return {'required':bool(reasons),'reasons':reasons}
