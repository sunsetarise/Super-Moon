from __future__ import annotations
from dataclasses import dataclass,field
import os,time,math,statistics
from typing import Callable,Any
from ..core import InvalidInput

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

try:
    import resource as _resource
except ImportError:  # Windows does not provide the POSIX resource module.
    _resource = None


def current_rss_bytes():
    try:
        with open('/proc/self/statm','r',encoding='ascii') as f:pages=int(f.read().split()[1])
        return pages*os.sysconf('SC_PAGE_SIZE')
    except (OSError,ValueError,IndexError):
        pass
    if _psutil is not None:
        try:return int(_psutil.Process(os.getpid()).memory_info().rss)
        except Exception:pass
    if _resource is not None:
        r=_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
        return int(r*(1024 if os.name!='darwin' else 1))
    return 0

@dataclass
class BenchmarkManager:
    records:list[dict]=field(default_factory=list)
    def run(self,name:str,fn:Callable,*args,repeats=3,**kwargs):
        if repeats<=0:raise InvalidInput('repeats must be positive')
        times=[];result=None
        for _ in range(repeats):
            t=time.perf_counter();result=fn(*args,**kwargs);times.append(time.perf_counter()-t)
        row={'name':name,'repeats':repeats,'min_s':min(times),'mean_s':statistics.mean(times),'max_s':max(times),'result':result};self.records.append(row);return row

@dataclass
class EnduranceManager:
    telemetry_interval:float=.25
    def run(self,duration_s:float,kernel:Callable[[int],Any]):
        duration=float(duration_s)
        if duration<=0:raise InvalidInput('duration_s must be positive')
        start=time.perf_counter();next_sample=start;iterations=0;errors=0;invariant_failures=0;samples=[]
        while True:
            now=time.perf_counter()
            if now-start>=duration:break
            try:
                out=kernel(iterations)
                if isinstance(out,dict) and out.get('invariant_ok') is False:invariant_failures+=1
            except Exception:
                errors+=1
            iterations+=1
            now=time.perf_counter()
            if now>=next_sample:
                samples.append({'t':now-start,'rss':current_rss_bytes()});next_sample=now+self.telemetry_interval
        elapsed=time.perf_counter()-start;rss=[x['rss'] for x in samples]
        slope=0.0
        if len(samples)>=2:
            tx=[x['t'] for x in samples];tm=statistics.mean(tx);rm=statistics.mean(rss);den=sum((x-tm)**2 for x in tx);slope=sum((x-tm)*(r-rm) for x,r in zip(tx,rss))/den if den else 0.0
        return {'elapsed_s':elapsed,'iterations':iterations,'iterations_per_s':iterations/elapsed if elapsed else math.inf,'errors':errors,'invariant_failures':invariant_failures,'samples':samples,'rss_min':min(rss) if rss else None,'rss_max':max(rss) if rss else None,'rss_drift':(rss[-1]-rss[0]) if len(rss)>=2 else 0,'rss_slope_bytes_s':slope,'status':'PASS' if errors==0 and invariant_failures==0 else 'FAIL'}
