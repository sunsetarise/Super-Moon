from __future__ import annotations
from pathlib import Path
import importlib.util, json, os, platform, shutil, time
import numpy as np

def capability_matrix():
    mods={'MPI':'mpi4py','PETSc':'petsc4py','SLEPc':'slepc4py','CUDA_CuPy':'cupy','Triton':'triton','NCCL_CuPy':'cupy'}
    out={'CPU':{'available':True,'status':'IMPLEMENTED'}}
    for k,m in mods.items(): out[k]={'available':importlib.util.find_spec(m) is not None,'status':'AVAILABLE_UNQUALIFIED' if importlib.util.find_spec(m) else 'HARDWARE_UNAVAILABLE'}
    out['nvcc']={'available':shutil.which('nvcc') is not None};out['nvidia_smi']={'available':shutil.which('nvidia-smi') is not None};out['mpiexec']={'available':shutil.which('mpiexec') is not None};return out

def mixed_precision_refinement(A,b,maxiter=10,tol=1e-12):
    A64=np.asarray(A,np.float64);b64=np.asarray(b,np.float64);x=np.linalg.solve(A64.astype(np.float32),b64.astype(np.float32)).astype(np.float64);hist=[]
    for _ in range(maxiter):
        r=b64-A64@x;rn=float(np.linalg.norm(r));hist.append(rn)
        if rn<tol:break
        d=np.linalg.solve(A64.astype(np.float32),r.astype(np.float32)).astype(np.float64);x+=d
    return x,hist

def roofline(flops,bytes_moved,peak_flops,bandwidth):
    I=flops/max(bytes_moved,1e-300);ceiling=min(peak_flops,I*bandwidth);return {'arithmetic_intensity':I,'ceiling':ceiling,'classification':'compute_bound' if peak_flops<=I*bandwidth else 'bandwidth_bound'}

def checkpoint(path,state):
    path=Path(path); np.savez_compressed(path,**{k:np.asarray(v) for k,v in state.items()});return path

def restart(path):
    z=np.load(path,allow_pickle=False);return {k:z[k] for k in z.files}


# ================= CELESTIAL DEPTH: HPC numerical / restart integrity =================
_capability_matrix_pre_celestial=capability_matrix

def capability_matrix():
    out=_capability_matrix_pre_celestial()
    # Presence stays explicitly distinct from qualification.
    for k,v in out.items():
        if isinstance(v,dict) and k!='CPU' and v.get('available') and 'status' not in v:
            v['status']='AVAILABLE_UNQUALIFIED'
    return out

def mixed_precision_refinement(A,b,maxiter=10,tol=1e-12):
    A64=np.asarray(A,np.float64);b64=np.asarray(b,np.float64);maxiter=int(maxiter);tol=float(tol)
    if A64.ndim!=2 or A64.shape[0]!=A64.shape[1] or b64.shape not in {(A64.shape[0],),(A64.shape[0],1)}: raise ValueError('square A and compatible b required')
    b64=b64.reshape(A64.shape[0])
    if not np.all(np.isfinite(A64)) or not np.all(np.isfinite(b64)): raise ValueError('A/b contain NaN/Inf')
    if maxiter<0 or tol<=0 or not np.isfinite(tol): raise ValueError('maxiter>=0 and finite tol>0 required')
    cond=float(np.linalg.cond(A64))
    if not np.isfinite(cond): raise np.linalg.LinAlgError('NUMERICAL_BREAKDOWN: singular/non-finite condition estimate')
    try: x=np.linalg.solve(A64.astype(np.float32),b64.astype(np.float32)).astype(np.float64)
    except np.linalg.LinAlgError as e: raise np.linalg.LinAlgError('NUMERICAL_BREAKDOWN: float32 correction system singular') from e
    hist=[]
    for _ in range(maxiter):
        r=b64-A64@x;rn=float(np.linalg.norm(r));hist.append(rn)
        if not np.isfinite(rn): raise FloatingPointError('NUMERICAL_BREAKDOWN: non-finite refinement residual')
        if rn<tol:break
        try: d=np.linalg.solve(A64.astype(np.float32),r.astype(np.float32)).astype(np.float64)
        except np.linalg.LinAlgError as e: raise np.linalg.LinAlgError('NUMERICAL_BREAKDOWN: correction solve singular') from e
        if not np.all(np.isfinite(d)): raise FloatingPointError('NUMERICAL_BREAKDOWN: non-finite correction')
        x+=d
    return x,hist

def roofline(flops,bytes_moved,peak_flops,bandwidth):
    vals=np.asarray([flops,bytes_moved,peak_flops,bandwidth],float)
    if np.any(~np.isfinite(vals)) or flops<0 or bytes_moved<=0 or peak_flops<=0 or bandwidth<=0: raise ValueError('finite flops>=0 and positive bytes/peak/bandwidth required')
    I=float(flops/bytes_moved);ceiling=float(min(peak_flops,I*bandwidth));return {'arithmetic_intensity':I,'ceiling':ceiling,'classification':'compute_bound' if peak_flops<=I*bandwidth else 'bandwidth_bound'}

def checkpoint(path,state):
    path=Path(path)
    if not isinstance(state,dict) or not state: raise ValueError('checkpoint state must be a non-empty dict')
    path.parent.mkdir(parents=True,exist_ok=True)
    arrays={k:np.asarray(v) for k,v in state.items()}
    if any(a.dtype==object for a in arrays.values()): raise ValueError('object arrays are not permitted in restart state')
    tmp=Path(str(path)+'.tmp.npz')
    np.savez_compressed(tmp,**arrays)
    os.replace(tmp,path)
    return path

def restart(path):
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(path)
    with np.load(path,allow_pickle=False) as z:
        return {k:z[k].copy() for k in z.files}
