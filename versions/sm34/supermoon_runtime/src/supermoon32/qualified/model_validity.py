from __future__ import annotations
from dataclasses import dataclass,field
from ..core import InvalidInput

@dataclass(frozen=True)
class ParameterRange:
    minimum:float; maximum:float; inclusive:bool=True
    def __post_init__(self):
        if self.maximum<=self.minimum:raise InvalidInput('parameter maximum must exceed minimum')
    def contains(self,x):
        v=float(x);return self.minimum<=v<=self.maximum if self.inclusive else self.minimum<v<self.maximum

@dataclass
class ModelValidityDomain:
    model_name:str; parameter_ranges:dict[str,ParameterRange]=field(default_factory=dict); assumptions:tuple[str,...]=(); unsupported_conditions:tuple[str,...]=(); expected_error_range:tuple[float,float]|None=None; required_input_quality:float=0.0; known_failure_modes:tuple[str,...]=()
    def assess(self,parameters:dict,input_quality:float=1.0,conditions=()):
        violations=[]
        for k,r in self.parameter_ranges.items():
            if k not in parameters:violations.append(f'missing:{k}')
            elif not r.contains(parameters[k]):violations.append(f'out_of_range:{k}')
        if not 0<=input_quality<=1:raise InvalidInput('input_quality must be in [0,1]')
        if input_quality<self.required_input_quality:violations.append('input_quality')
        bad=set(map(str,conditions)) & set(self.unsupported_conditions)
        violations.extend(f'unsupported:{x}' for x in sorted(bad))
        return {'valid':not violations,'violations':violations,'model':self.model_name}
