from __future__ import annotations
import time,tracemalloc

def benchmark(fn,*args,repeats=3,**kwargs):
    times=[];peaks=[];out=None
    for _ in range(repeats):
        tracemalloc.start();t=time.perf_counter();out=fn(*args,**kwargs);times.append(time.perf_counter()-t);_,peak=tracemalloc.get_traced_memory();peaks.append(peak);tracemalloc.stop()
    return {'min_time':min(times),'mean_time':sum(times)/len(times),'max_time':max(times),'peak_memory':max(peaks),'repeats':repeats,'result':out}
