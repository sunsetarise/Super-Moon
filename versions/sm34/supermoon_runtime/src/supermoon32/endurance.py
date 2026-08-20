from __future__ import annotations
import time,os,json
from pathlib import Path
import numpy as np
from .sparse import as_csr,cg
from .optimization import bfgs
from .ode import rk4
from .cfd import euler_2d_cartesian,cons2d
from .fea import bar1d
from .geometry import orientation2d
try:import psutil
except Exception:psutil=None

def telemetry():
    if psutil:
        p=psutil.Process();m=p.memory_info();return {'time':time.time(),'rss':m.rss,'vms':m.vms,'threads':p.num_threads(),'fds':p.num_fds() if hasattr(p,'num_fds') else None}
    return {'time':time.time(),'rss':None,'vms':None,'threads':None,'fds':None}
def mixed_iteration(seed=0):
    rng=np.random.default_rng(seed);A=rng.normal(size=(8,8));A=A.T@A+np.eye(8);b=rng.normal(size=8);r=cg(as_csr(A),b,tol=1e-9,max_iter=100)
    o=bfgs(lambda x:(x[0]-1)**2+2*(x[1]+2)**2,[0,0],tol=1e-7,max_iter=30)
    od=rk4(lambda t,y:-y,(0,.05),[1.],.01)
    rho=np.ones((4,4));u=np.zeros_like(rho);v=np.zeros_like(rho);p=np.ones_like(rho);U=cons2d(rho,u,v,p);cf=euler_2d_cartesian(U,.25,.25,.002)
    ba=bar1d([0,1],[(0,1)],2e11,1e-4,{1:1000},[0]);ori=orientation2d([0,0],[1,0],[0,1])
    bad=not(r.converged and o.converged and np.all(np.isfinite(od.y)) and cf.min_density>0 and ba.residual_norm<1e-8 and ori==1)
    return {'bad':bad,'cg_residual':r.residual_norm,'opt_residual':o.residual_norm,'cfd_steps':cf.steps}
def run_endurance(duration_seconds,sample_interval=.5,report_path=None):
    duration_seconds=float(duration_seconds)
    if duration_seconds<=0:raise ValueError('positive duration required')
    start=time.monotonic();last=start;rows=[telemetry()];iters=errors=invariants=0
    while time.monotonic()-start<duration_seconds:
        try:
            rr=mixed_iteration(iters)
            if rr['bad']:invariants+=1
        except Exception:errors+=1
        iters+=1;now=time.monotonic()
        if now-last>=sample_interval:rows.append(telemetry());last=now
    elapsed=time.monotonic()-start;rss=[x['rss'] for x in rows if x['rss'] is not None];rep={'requested_seconds':duration_seconds,'elapsed_seconds':elapsed,'iterations':iters,'iterations_per_second':iters/elapsed,'errors':errors,'invariant_failures':invariants,'telemetry':rows,'rss_min':min(rss) if rss else None,'rss_max':max(rss) if rss else None,'rss_drift':rss[-1]-rss[0] if len(rss)>1 else 0,'passed':errors==0 and invariants==0 and elapsed>=duration_seconds}
    if report_path:Path(report_path).write_text(json.dumps(rep,indent=2),encoding='utf-8')
    return rep
