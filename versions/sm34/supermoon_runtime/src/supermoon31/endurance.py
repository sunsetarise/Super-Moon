from __future__ import annotations
from pathlib import Path
import json,os,time,threading
import numpy as np
try: import psutil
except Exception: psutil=None
from .fea import truss2d
from .cfd import sod_initial,euler_1d
from .hpc import mixed_precision_refinement

def telemetry():
    d={'time':time.time(),'threads':threading.active_count()}
    if psutil:
        p=psutil.Process();m=p.memory_info();d.update({'rss':m.rss,'vms':m.vms,'cpu_percent':p.cpu_percent(None),'fds':getattr(p,'num_fds',lambda:None)()})
    return d

def mixed_iteration(seed=0):
    rng=np.random.default_rng(seed); A=rng.normal(size=(12,12));A=A.T@A+np.eye(12);b=rng.normal(size=12);x,h=mixed_precision_refinement(A,b)
    tr=truss2d([[0,0],[1,0],[1,1]],[(0,1),(1,2),(0,2)],2e11,1e-4,{5:-1e3},[0,1,3])
    # Qualification Patch 1 deliberately exercises both Euler orders during
    # endurance: even seeds use first order, odd seeds use repaired MUSCL.
    second_order=bool(int(seed)%2);xx=np.linspace(0,1,40);cf=euler_1d(xx,sod_initial(xx),.002,second_order=second_order)
    return {'linear_residual':float(np.linalg.norm(A@x-b)),'fea_residual':tr.residual_norm,'cfd_steps':cf.metadata['steps'],'cfd_second_order':second_order}

def run_endurance(duration_seconds,report_path=None,sample_interval=1.0):
    if duration_seconds<=0: raise ValueError('duration must be positive real elapsed time')
    start=time.monotonic();rows=[];iters=0;errors=[]
    while time.monotonic()-start < duration_seconds:
        try:mixed_iteration(iters)
        except Exception as e:errors.append(repr(e))
        iters+=1
        if not rows or time.time()-rows[-1]['time']>=sample_interval: rows.append(telemetry())
    elapsed=time.monotonic()-start; report={'requested_seconds':duration_seconds,'elapsed_seconds':elapsed,'iterations':iters,'errors':errors,'telemetry':rows,'passed':elapsed>=duration_seconds and not errors}
    if report_path: Path(report_path).write_text(json.dumps(report,indent=2))
    return report


# ================= CELESTIAL DEPTH: endurance truth / telemetry semantics =================
def telemetry():
    d={'time':time.time(),'monotonic':time.monotonic(),'threads':threading.active_count()}
    if psutil:
        p=psutil.Process();m=p.memory_info();d.update({'rss':m.rss,'vms':m.vms,'cpu_percent':p.cpu_percent(None),'fds':getattr(p,'num_fds',lambda:None)()})
    return d

def run_endurance(duration_seconds,report_path=None,sample_interval=1.0):
    duration_seconds=float(duration_seconds);sample_interval=float(sample_interval)
    if not np.isfinite([duration_seconds,sample_interval]).all() or duration_seconds<=0 or sample_interval<=0: raise ValueError('duration and sample_interval must be positive finite real time')
    start=time.monotonic();rows=[];iters=0;errors=[];invariant_failures=[];last_sample=-float('inf')
    while time.monotonic()-start < duration_seconds:
        try:
            r=mixed_iteration(iters)
            if r['linear_residual']>1e-7: invariant_failures.append({'iteration':iters,'kind':'linear_residual','value':r['linear_residual']})
            if r['fea_residual']>1e-6: invariant_failures.append({'iteration':iters,'kind':'fea_residual','value':r['fea_residual']})
        except Exception as e:errors.append({'iteration':iters,'error':repr(e)})
        iters+=1;now=time.monotonic()
        if now-last_sample>=sample_interval:rows.append(telemetry());last_sample=now
    elapsed=time.monotonic()-start
    rss=[r.get('rss') for r in rows if r.get('rss') is not None]
    report={'requested_seconds':duration_seconds,'elapsed_seconds':elapsed,'iterations':iters,'iterations_per_second':iters/max(elapsed,np.finfo(float).tiny),'cfd_first_order_iterations':(iters+1)//2,'cfd_second_order_iterations':iters//2,'errors':errors,'invariant_failures':invariant_failures,'telemetry':rows,'rss_min':min(rss) if rss else None,'rss_max':max(rss) if rss else None,'rss_drift':(rss[-1]-rss[0]) if len(rss)>=2 else 0 if rss else None,'passed':elapsed>=duration_seconds and not errors and not invariant_failures,'qualification_scope':'EXECUTED_DURATION_ONLY','cfd_order_mix':'alternating first/second order by iteration seed parity'}
    if report_path:
        p=Path(report_path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
