from __future__ import annotations
from dataclasses import dataclass,asdict,field
import hashlib,json,time
@dataclass
class Requirement:
    req_id:str; title:str; text:str; source:str=''; revision:str='A'; rationale:str=''; parent:str|None=None; children:list[str]=field(default_factory=list); criticality:str=''; verification_method:str='ANALYSIS'; status:str='OPEN'; owner:str=''; evidence:list[str]=field(default_factory=list)
class RequirementsDB:
    def __init__(self): self.req={};self.links=[]
    def add(self,r:Requirement):
        if r.req_id in self.req: raise KeyError(r.req_id)
        self.req[r.req_id]=r;return r
    def link(self,a,b,relation='traces_to'):
        if a not in self.req or b not in self.req: raise KeyError('unknown requirement')
        self.links.append((a,relation,b))
    def orphan_critical(self):
        linked={a for a,_,b in self.links}|{b for a,_,b in self.links};return [r.req_id for r in self.req.values() if r.criticality.upper() in ('HIGH','CRITICAL') and r.req_id not in linked and not r.evidence]
    def validate(self):
        issues=[]
        for r in self.req.values():
            if not r.text.strip():issues.append((r.req_id,'empty'))
            if r.verification_method not in {'ANALYSIS','TEST','INSPECTION','DEMONSTRATION','SIMULATION','REVIEW'}:issues.append((r.req_id,'invalid verification method'))
        return issues

def fault_tree(node):
    if isinstance(node,(int,float)): return float(node)
    op=node['op'].upper(); vals=[fault_tree(x) for x in node['children']]
    if op=='AND':
        p=1.0
        for v in vals:p*=v
        return p
    if op=='OR':
        q=1.0
        for v in vals:q*=1-v
        return 1-q
    raise ValueError(op)

class AuditChain:
    def __init__(self): self.events=[]
    def append(self,actor,operation,input_obj,output_obj,status='OK',reason=''):
        prev=self.events[-1]['hash'] if self.events else '0'*64; payload={'timestamp':time.time(),'actor':actor,'operation':operation,'input':input_obj,'previous_hash':prev,'output':output_obj,'status':status,'reason':reason};h=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest();payload['hash']=h;self.events.append(payload);return payload
    def verify(self):
        prev='0'*64
        for ev in self.events:
            if ev['previous_hash']!=prev:return False
            d={k:v for k,v in ev.items() if k!='hash'};h=hashlib.sha256(json.dumps(d,sort_keys=True,default=str).encode()).hexdigest()
            if h!=ev['hash']:return False
            prev=h
        return True


# ================= CELESTIAL DEPTH: evidence / probability truth contracts =================
_RequirementsDB_validate_pre_celestial=RequirementsDB.validate

def _celestial_requirements_validate(self):
    issues=list(_RequirementsDB_validate_pre_celestial(self))
    known=set(self.req)
    seen_links=set()
    for a,rel,b in self.links:
        if a not in known or b not in known: issues.append((f'{a}->{b}','dangling link'))
        key=(a,rel,b)
        if key in seen_links: issues.append((f'{a}->{b}','duplicate link'))
        seen_links.add(key)
    for r in self.req.values():
        if r.parent is not None and r.parent not in known: issues.append((r.req_id,'unknown parent'))
        for c in r.children:
            if c not in known: issues.append((r.req_id,f'unknown child {c}'))
        if r.status not in {'OPEN','IN_WORK','VERIFIED','VALIDATED','CLOSED','WAIVED'}: issues.append((r.req_id,'invalid status'))
    return issues
RequirementsDB.validate=_celestial_requirements_validate

def fault_tree(node):
    if isinstance(node,(int,float)):
        p=float(node)
        if not __import__('math').isfinite(p) or not 0<=p<=1: raise ValueError('basic-event probability must be within [0,1]')
        return p
    if not isinstance(node,dict) or 'op' not in node or 'children' not in node or not node['children']: raise ValueError('fault-tree gate requires op and non-empty children')
    op=str(node['op']).upper();vals=[fault_tree(x) for x in node['children']]
    if op=='AND': return float(__import__('math').prod(vals))
    if op=='OR': return float(1.0-__import__('math').prod([1-v for v in vals]))
    raise ValueError(f'unsupported gate {op}')

def _audit_canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),default=str).encode('utf-8')

def _celestial_audit_append(self,actor,operation,input_obj,output_obj,status='OK',reason=''):
    if not str(actor).strip() or not str(operation).strip(): raise ValueError('actor and operation are required')
    prev=self.events[-1]['hash'] if self.events else '0'*64
    payload={'timestamp':time.time(),'actor':actor,'operation':operation,'input':input_obj,'previous_hash':prev,'output':output_obj,'status':status,'reason':reason}
    payload['hash']=hashlib.sha256(_audit_canonical(payload)).hexdigest();self.events.append(payload);return payload

def _celestial_audit_verify(self):
    prev='0'*64
    for ev in self.events:
        if not isinstance(ev,dict) or ev.get('previous_hash')!=prev or 'hash' not in ev:return False
        d={k:v for k,v in ev.items() if k!='hash'}
        if hashlib.sha256(_audit_canonical(d)).hexdigest()!=ev['hash']:return False
        prev=ev['hash']
    return True
AuditChain.append=_celestial_audit_append
AuditChain.verify=_celestial_audit_verify
