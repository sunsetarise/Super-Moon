from __future__ import annotations
from dataclasses import dataclass
import itertools,math
from .core import InvalidInput
@dataclass
class DiscoveryResult:
    candidate:object;score:float;evaluated:int;history:list
def exhaustive_discovery(search_space,evaluator,minimize=True,max_evals=None):
    best=None;bs=math.inf if minimize else -math.inf;hist=[];n=0
    for c in search_space:
        s=float(evaluator(c));n+=1;hist.append((c,s))
        if (minimize and s<bs) or ((not minimize) and s>bs):best,bs=c,s
        if max_evals is not None and n>=max_evals:break
    if n==0:raise InvalidInput('empty search space')
    return DiscoveryResult(best,bs,n,hist)
def expression_program_search(constants,ops,target,max_depth=2):
    vals=[(str(c),float(c)) for c in constants];allv=list(vals)
    best=(None,math.inf,None);evaluated=0
    for _ in range(max_depth):
        nxt=[]
        for (ea,a),(eb,b) in itertools.product(allv,allv):
            for name,op in ops.items():
                try:v=float(op(a,b))
                except Exception:continue
                if not math.isfinite(v):continue
                e=f'({ea}{name}{eb})';err=abs(v-target);evaluated+=1
                if err<best[1]:best=(e,err,v)
                nxt.append((e,v))
        allv=(allv+nxt)[-500:]
        if best[1]==0:break
    return {'expression':best[0],'error':best[1],'value':best[2],'evaluated':evaluated}
