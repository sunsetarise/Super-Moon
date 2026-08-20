from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .enums import ScaleClass
from .risk import classify_scale
from ..core import InvalidInput

@dataclass(frozen=True)
class ResourceEstimate:
    problem_units:float; bytes_per_unit:float; overhead_factor:float=1.5; communication_bytes:float=0.0
    @property
    def memory_bytes(self):return float(self.problem_units*self.bytes_per_unit*self.overhead_factor)

@dataclass(frozen=True)
class HPCRoute:
    scale:ScaleClass; backend:str; distributed_required:bool; rationale:tuple[str,...]

def route_hpc(problem_units,available_ram_bytes,bytes_per_unit=256,distributed_available=False,gpu_memory_bytes=0):
    est=ResourceEstimate(float(problem_units),float(bytes_per_unit));mem=est.memory_bytes;scale=classify_scale(problem_units,distributed=mem>available_ram_bytes)
    reasons=[f'estimated_memory={mem:.0f}',f'available_ram={available_ram_bytes:.0f}']
    if mem<=gpu_memory_bytes and gpu_memory_bytes>0 and scale<=ScaleClass.S4_SINGLE_NODE_HPC:return HPCRoute(scale,'GPU_CANDIDATE',False,tuple(reasons))
    if mem<=available_ram_bytes:return HPCRoute(scale,'CPU_SINGLE_NODE',False,tuple(reasons))
    if distributed_available:return HPCRoute(max(scale,ScaleClass.S5_MULTI_NODE_HPC),'DISTRIBUTED_HPC',True,tuple(reasons))
    return HPCRoute(max(scale,ScaleClass.S5_MULTI_NODE_HPC),'EXTERNAL_DISTRIBUTED_TOOL_REQUIRED',True,tuple(reasons))

def strong_scaling(times):
    rows=[];items=sorted((int(k),float(v)) for k,v in dict(times).items())
    if not items or items[0][0]!=1 or any(t<=0 for _,t in items):raise InvalidInput('strong scaling requires positive time at p=1 and positive times')
    t1=items[0][1]
    for p,t in items:rows.append({'workers':p,'time':t,'speedup':t1/t,'efficiency':t1/(t*p)})
    return rows

def weak_scaling(times):
    items=sorted((int(k),float(v)) for k,v in dict(times).items())
    if not items or items[0][0]!=1 or any(t<=0 for _,t in items):raise InvalidInput('weak scaling requires p=1 baseline and positive times')
    t1=items[0][1];return [{'workers':p,'time':t,'efficiency':t1/t} for p,t in items]

def load_imbalance(workloads):
    w=np.asarray(workloads,float)
    if w.size==0 or np.mean(w)<=0:raise InvalidInput('positive workloads required')
    return float((np.max(w)-np.mean(w))/np.mean(w))
