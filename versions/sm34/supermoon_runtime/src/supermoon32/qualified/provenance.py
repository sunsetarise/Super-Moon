from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json
from collections import defaultdict,deque
from ..core import InvalidInput

def sha256_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha256_file(path)->str:return sha256_bytes(Path(path).read_bytes())

@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id:str; role:str; sha256:str; bytes:int; metadata:dict
    @classmethod
    def from_file(cls,artifact_id,role,path,metadata=None):
        p=Path(path);b=p.read_bytes();return cls(str(artifact_id),str(role),sha256_bytes(b),len(b),metadata or {})

class ProvenanceGraph:
    def __init__(self):self.artifacts:dict[str,ArtifactRecord]={};self.edges:list[tuple[str,str,str]]=[]
    def add_artifact(self,a:ArtifactRecord):
        if a.artifact_id in self.artifacts:raise InvalidInput('duplicate artifact id')
        self.artifacts[a.artifact_id]=a;return a
    def add_edge(self,source,target,operation):
        if source not in self.artifacts or target not in self.artifacts:raise InvalidInput('provenance edge references unknown artifact')
        self.edges.append((source,target,str(operation)))
    def trace_to(self,target):
        if target not in self.artifacts:raise InvalidInput('unknown target artifact')
        parents=defaultdict(list)
        for a,b,op in self.edges:parents[b].append((a,op))
        seen=set();stack=[target]
        while stack:
            n=stack.pop()
            for p,_ in parents[n]:
                if p not in seen:seen.add(p);stack.append(p)
        return seen
    def to_dict(self):return {'artifacts':{k:asdict(v) for k,v in self.artifacts.items()},'edges':[{'source':a,'target':b,'operation':op} for a,b,op in self.edges]}
