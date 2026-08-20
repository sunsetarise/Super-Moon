from __future__ import annotations
import os,time,platform,concurrent.futures,multiprocessing as mp
import numpy as np
from .core import BackendUnavailable

def capability_matrix():
    out={'serial':'IMPLEMENTED','vectorized':'IMPLEMENTED','threaded_cpu':'IMPLEMENTED','multiprocess':'IMPLEMENTED','mpi':'UNAVAILABLE_ENVIRONMENT','gpu':'UNAVAILABLE_ENVIRONMENT','cpu_count':os.cpu_count(),'platform':platform.platform()}
    try:import mpi4py;out['mpi']='IMPLEMENTED_UNEXECUTED'
    except Exception:out['mpi']='UNAVAILABLE_ENVIRONMENT'
    try:import cupy;out['gpu']='IMPLEMENTED_UNEXECUTED'
    except Exception:out['gpu']='UNAVAILABLE_ENVIRONMENT'
    return out
def threaded_map(fn,items,max_workers=None):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:return list(ex.map(fn,items))
def multiprocess_map(fn,items,max_workers=None):
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as ex:return list(ex.map(fn,items))
def benchmark_scaling(fn,arg,workers=(1,2,4),repeats=1,backend='thread'):
    rows=[]
    for p in workers:
        t=time.perf_counter()
        if p==1:[fn(arg) for _ in range(repeats)]
        elif backend=='thread':threaded_map(fn,[arg]*repeats,p)
        else:multiprocess_map(fn,[arg]*repeats,p)
        dt=time.perf_counter()-t;rows.append({'workers':p,'time':dt})
    t1=rows[0]['time']
    for r in rows:r['speedup']=t1/r['time'] if r['time'] else float('inf');r['efficiency']=r['speedup']/r['workers']
    return rows
def mpi_status():
    try:
        from mpi4py import MPI;return {'available':True,'rank':MPI.COMM_WORLD.Get_rank(),'size':MPI.COMM_WORLD.Get_size()}
    except Exception:return {'available':False,'status':'UNAVAILABLE_ENVIRONMENT'}
def gpu_status():
    try:
        import cupy as cp;dev=cp.cuda.Device();return {'available':True,'device':int(dev.id),'name':cp.cuda.runtime.getDeviceProperties(dev.id)['name'].decode()}
    except Exception:return {'available':False,'status':'UNAVAILABLE_ENVIRONMENT'}
