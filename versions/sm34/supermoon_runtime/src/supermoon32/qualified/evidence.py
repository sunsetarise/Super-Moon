from __future__ import annotations
from dataclasses import dataclass,field,asdict
from .enums import ClaimLevel,MaturityLevel,QualificationLevel
from ..core import InvalidInput

@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id:str; kind:str; status:str; artifact_hash:str=''; metadata:dict=field(default_factory=dict)

@dataclass
class ClaimRecord:
    claim_id:str; text:str; requested_level:ClaimLevel; evidence_ids:list[str]=field(default_factory=list); status:str='UNASSESSED'; granted_level:ClaimLevel|None=None

LEVEL_REQUIREMENTS={
    ClaimLevel.IMPLEMENTED:{'implementation'},
    ClaimLevel.TESTED:{'implementation','test'},
    ClaimLevel.NUMERICALLY_VERIFIED:{'implementation','test','verification'},
    ClaimLevel.VALIDATED:{'implementation','test','verification','validation'},
    ClaimLevel.BENCHMARKED:{'implementation','test','verification','benchmark'},
    ClaimLevel.STRESS_TESTED:{'implementation','test','verification','stress'},
    ClaimLevel.ENDURANCE_TESTED:{'implementation','test','verification','endurance'},
    ClaimLevel.EXTERNALLY_REPRODUCED:{'implementation','test','verification','external_reproduction'},
    ClaimLevel.INDUSTRIALLY_VALIDATED:{'implementation','test','verification','validation','industrial_validation'},
    ClaimLevel.CERTIFICATION_ACCEPTABLE:{'implementation','test','verification','validation','certification_acceptance'},
}

class EvidenceEngine:
    def __init__(self):self.evidence:dict[str,EvidenceRecord]={};self.claims:dict[str,ClaimRecord]={}
    def add_evidence(self,e:EvidenceRecord):
        if not e.evidence_id or e.evidence_id in self.evidence:raise InvalidInput('evidence id must be unique and non-empty')
        self.evidence[e.evidence_id]=e;return e
    def add_claim(self,c:ClaimRecord):
        if not c.claim_id or c.claim_id in self.claims:raise InvalidInput('claim id must be unique and non-empty')
        self.claims[c.claim_id]=c;return c
    def evaluate(self,claim_id:str)->ClaimRecord:
        c=self.claims[claim_id];records=[self.evidence[x] for x in c.evidence_ids if x in self.evidence and self.evidence[x].status=='PASS'];kinds={e.kind for e in records}
        granted=None
        for level in ClaimLevel:
            if LEVEL_REQUIREMENTS[level] <= kinds:granted=level
        c.granted_level=granted;c.status='PASS' if granted is not None and granted>=c.requested_level else 'INSUFFICIENT_EVIDENCE';return c
    def to_dict(self):return {'evidence':{k:asdict(v) for k,v in self.evidence.items()},'claims':{k:asdict(v) for k,v in self.claims.items()}}

@dataclass
class CapabilityQualification:
    capability_id:str; maturity:MaturityLevel; qualification:QualificationLevel; validity_domain:dict=field(default_factory=dict); limitations:list[str]=field(default_factory=list); evidence_ids:list[str]=field(default_factory=list)

class QualificationLedger:
    def __init__(self):self.entries:dict[str,CapabilityQualification]={}
    def set(self,e:CapabilityQualification):self.entries[e.capability_id]=e;return e
    def get(self,key):return self.entries[key]
    def require(self,key,maturity:MaturityLevel|None=None,qualification:QualificationLevel|None=None):
        e=self.entries[key]
        if maturity is not None and e.maturity<maturity:return False
        if qualification is not None and e.qualification<qualification:return False
        return True
