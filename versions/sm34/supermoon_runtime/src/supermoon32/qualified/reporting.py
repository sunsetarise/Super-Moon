from __future__ import annotations
from dataclasses import dataclass,field,asdict
import json
from .enums import ConfidenceClass

@dataclass
class MachineReadableReport:
    problem_id:str; cri:float; tool_route:list[str]; verification_status:str; validation_status:str; uncertainty:dict=field(default_factory=dict); discrepancies:list=field(default_factory=list); confidence:ConfidenceClass=ConfidenceClass.C0_UNASSESSED; limitations:list[str]=field(default_factory=list); evidence:list[str]=field(default_factory=list); metadata:dict=field(default_factory=dict)
    def to_dict(self):
        d=asdict(self);d['confidence']=self.confidence.name;return d
    def to_json(self):return json.dumps(self.to_dict(),indent=2,sort_keys=True,default=str)

def executive_summary(report:MachineReadableReport):
    return {'problem_id':report.problem_id,'CRI':report.cri,'verification':report.verification_status,'validation':report.validation_status,'confidence':report.confidence.name,'limitations_count':len(report.limitations),'evidence_count':len(report.evidence)}
