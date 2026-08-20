from __future__ import annotations
from dataclasses import dataclass,field,asdict
from collections import defaultdict,deque
from typing import Callable,Any,Iterable
import time,uuid
from ..core import InvalidInput

@dataclass
class WorkflowNode:
    node_id:str; fn:Callable[...,Any]; dependencies:tuple[str,...]=(); kwargs:dict=field(default_factory=dict); retries:int=0

@dataclass
class NodeRun:
    node_id:str; status:str; attempts:int; elapsed_s:float; result:Any=None; error:str|None=None

class WorkflowGraph:
    def __init__(self):self.nodes:dict[str,WorkflowNode]={}
    def add(self,node:WorkflowNode):
        if not node.node_id or node.node_id in self.nodes:raise InvalidInput('workflow node id must be unique and non-empty')
        self.nodes[node.node_id]=node;return node
    def order(self):
        indeg={k:0 for k in self.nodes};children=defaultdict(list)
        for k,n in self.nodes.items():
            for d in n.dependencies:
                if d not in self.nodes:raise InvalidInput(f'missing workflow dependency: {d}')
                indeg[k]+=1;children[d].append(k)
        q=deque(sorted(k for k,v in indeg.items() if v==0));out=[]
        while q:
            n=q.popleft();out.append(n)
            for c in sorted(children[n]):
                indeg[c]-=1
                if indeg[c]==0:q.append(c)
        if len(out)!=len(self.nodes):raise InvalidInput('workflow graph contains cycle')
        return out
    def execute(self,initial_context:dict|None=None,fail_fast=True):
        ctx=dict(initial_context or {});runs=[]
        for node_id in self.order():
            n=self.nodes[node_id];attempts=0;t=time.perf_counter();err=None;res=None
            while attempts<=n.retries:
                attempts+=1
                try:
                    deps={d:ctx[d] for d in n.dependencies};res=n.fn(dependencies=deps,context=ctx,**n.kwargs);err=None;break
                except Exception as e:
                    err=f'{type(e).__name__}: {e}'
            elapsed=time.perf_counter()-t
            if err is not None:
                runs.append(NodeRun(node_id,'FAIL',attempts,elapsed,None,err))
                if fail_fast:return {'status':'FAIL','context':ctx,'runs':runs}
            else:
                ctx[node_id]=res;runs.append(NodeRun(node_id,'PASS',attempts,elapsed,res,None))
        return {'status':'PASS' if all(r.status=='PASS' for r in runs) else 'FAIL','context':ctx,'runs':runs}

@dataclass
class ExperimentPlan:
    hypothesis:str; parameters:dict; parameter_ranges:dict; solver:str; metrics:tuple[str,...]; replications:int=1; seed:int=0; tolerances:dict=field(default_factory=dict); acceptance_criteria:dict=field(default_factory=dict)
    def validate(self):
        if not self.hypothesis or not self.solver:raise InvalidInput('hypothesis and solver required')
        if self.replications<=0:raise InvalidInput('replications must be positive')
        return True

def factorial_sweep(parameter_values:dict[str,Iterable[Any]]):
    import itertools
    names=list(parameter_values);vals=[list(parameter_values[n]) for n in names]
    if any(not v for v in vals):raise InvalidInput('parameter sweeps cannot contain empty value lists')
    return [dict(zip(names,combo)) for combo in itertools.product(*vals)]

def new_run_id(prefix='SM32Q')->str:return f'{prefix}-{uuid.uuid4().hex}'
