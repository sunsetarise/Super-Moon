from __future__ import annotations
from dataclasses import dataclass
import time, numpy as np
from .core import *
@dataclass
class COO:
    row: np.ndarray; col: np.ndarray; data: np.ndarray; shape: tuple[int,int]
    def __post_init__(self):
        self.row=np.asarray(self.row,int);self.col=np.asarray(self.col,int);self.data=np.asarray(self.data,float)
        if not(len(self.row)==len(self.col)==len(self.data)):raise DimensionMismatch('COO arrays differ')
        if np.any(self.row<0) or np.any(self.col<0) or np.any(self.row>=self.shape[0]) or np.any(self.col>=self.shape[1]):raise InvalidInput('COO index out of range')
    def to_csr(self):
        order=np.lexsort((self.col,self.row));r=self.row[order];c=self.col[order];d=self.data[order];indptr=np.zeros(self.shape[0]+1,dtype=int);np.add.at(indptr,r+1,1);np.cumsum(indptr,out=indptr);return CSR(indptr,c,d,self.shape)
    def to_dense(self):
        a=np.zeros(self.shape);np.add.at(a,(self.row,self.col),self.data);return a
@dataclass
class CSR:
    indptr: np.ndarray; indices: np.ndarray; data: np.ndarray; shape: tuple[int,int]
    def __post_init__(self):
        self.indptr=np.asarray(self.indptr,int);self.indices=np.asarray(self.indices,int);self.data=np.asarray(self.data,float)
        if len(self.indptr)!=self.shape[0]+1 or self.indptr[0]!=0 or self.indptr[-1]!=len(self.data):raise InvalidInput('invalid CSR indptr')
        if len(self.indices)!=len(self.data):raise DimensionMismatch('CSR index/data mismatch')
    def matvec(self,x):
        x=finite_array(x,'x',1)
        if len(x)!=self.shape[1]:raise DimensionMismatch('matvec dimension mismatch')
        y=np.zeros(self.shape[0])
        for i in range(self.shape[0]):
            a,b=self.indptr[i],self.indptr[i+1];y[i]=self.data[a:b]@x[self.indices[a:b]]
        return y
    def diagonal(self):
        d=np.zeros(min(self.shape))
        for i in range(len(d)):
            a,b=self.indptr[i],self.indptr[i+1];mask=self.indices[a:b]==i
            if np.any(mask):d[i]=self.data[a:b][np.flatnonzero(mask)[0]]
        return d
    def to_dense(self):
        a=np.zeros(self.shape)
        for i in range(self.shape[0]):
            p,q=self.indptr[i],self.indptr[i+1];np.add.at(a[i],self.indices[p:q],self.data[p:q])
        return a
@dataclass
class CSC:
    indptr: np.ndarray; indices: np.ndarray; data: np.ndarray; shape: tuple[int,int]
    @classmethod
    def from_coo(cls,coo:COO):
        return cls(*_csc_parts(coo),coo.shape)
    def to_dense(self):
        a=np.zeros(self.shape)
        for j in range(self.shape[1]):
            p,q=self.indptr[j],self.indptr[j+1];np.add.at(a[:,j],self.indices[p:q],self.data[p:q])
        return a
def _csc_parts(coo):
    order=np.lexsort((coo.row,coo.col));c=coo.col[order];r=coo.row[order];d=coo.data[order];ip=np.zeros(coo.shape[1]+1,dtype=int);np.add.at(ip,c+1,1);np.cumsum(ip,out=ip);return ip,r,d
def as_csr(A):
    if isinstance(A,CSR):return A
    a=finite_array(A,'A',2);r,c=np.nonzero(a);return COO(r,c,a[r,c],a.shape).to_csr()
def jacobi_preconditioner(A):
    A=as_csr(A);d=A.diagonal()
    if np.any(np.abs(d)<=np.finfo(float).tiny):raise SingularSystem('zero diagonal')
    return lambda r:r/d
def cg(A,b,x0=None,tol=1e-10,max_iter=None,M=None):
    A=as_csr(A);b=finite_array(b,'b',1);n=len(b);x=np.zeros(n) if x0 is None else finite_array(x0,'x0',1).copy();max_iter=10*n if max_iter is None else int(max_iter)
    if max_iter<=0: raise InvalidInput('max_iter must be positive')
    t=time.perf_counter();hist=[]
    r=b-A.matvec(x);z=r.copy() if M is None else M(r);p=z.copy();rz=float(r@z)
    for k in range(max_iter+1):
        rn=float(np.linalg.norm(r));hist.append(rn)
        if rn<=tol*(np.linalg.norm(b)+1):return SolverResult(x,True,k,rn,'tolerance',time.perf_counter()-t,history=hist)
        if k==max_iter:break
        Ap=A.matvec(p);den=float(p@Ap)
        if den<=0:raise ConvergenceFailure('CG requires SPD operator')
        alpha=rz/den;x+=alpha*p;r-=alpha*Ap;z=r.copy() if M is None else M(r);rz2=float(r@z);p=z+(rz2/rz)*p;rz=rz2
    return SolverResult(x,False,max_iter,hist[-1],'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')
def gmres(A,b,x0=None,tol=1e-10,max_iter=None,restart=30):
    A=as_csr(A);b=finite_array(b,'b',1);n=len(b);x=np.zeros(n) if x0 is None else np.asarray(x0,float).copy();max_iter=10*n if max_iter is None else int(max_iter)
    if max_iter<=0: raise InvalidInput('max_iter must be positive')
    t=time.perf_counter();hist=[];total=0
    while total<max_iter:
        r=b-A.matvec(x); beta=float(np.linalg.norm(r));hist.append(beta)
        if beta<=tol*(np.linalg.norm(b)+1):return SolverResult(x,True,total,beta,'tolerance',time.perf_counter()-t,history=hist)
        m=min(restart,max_iter-total);V=np.zeros((n,m+1));H=np.zeros((m+1,m));V[:,0]=r/beta;g=np.zeros(m+1);g[0]=beta
        for j in range(m):
            w=A.matvec(V[:,j])
            for i in range(j+1):H[i,j]=V[:,i]@w;w-=H[i,j]*V[:,i]
            H[j+1,j]=np.linalg.norm(w)
            if H[j+1,j]>0:V[:,j+1]=w/H[j+1,j]
            y=np.linalg.lstsq(H[:j+2,:j+1],g[:j+2],rcond=None)[0];res=np.linalg.norm(g[:j+2]-H[:j+2,:j+1]@y);hist.append(float(res));total+=1
            if res<=tol*(np.linalg.norm(b)+1):x+=V[:,:j+1]@y;return SolverResult(x,True,total,float(res),'tolerance',time.perf_counter()-t,history=hist)
        y=np.linalg.lstsq(H[:m+1,:m],g[:m+1],rcond=None)[0];x+=V[:,:m]@y
    rn=float(np.linalg.norm(b-A.matvec(x)));return SolverResult(x,False,total,rn,'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')
def bicgstab(A,b,x0=None,tol=1e-10,max_iter=None):
    A=as_csr(A);b=finite_array(b,'b',1);n=len(b);x=np.zeros(n) if x0 is None else np.asarray(x0,float).copy();max_iter=10*n if max_iter is None else int(max_iter)
    if max_iter<=0: raise InvalidInput('max_iter must be positive')
    r=b-A.matvec(x);rh=r.copy();rho=alpha=omega=1.;v=np.zeros(n);p=np.zeros(n);hist=[];t=time.perf_counter()
    for k in range(1,max_iter+1):
        rho1=float(rh@r)
        if abs(rho1)<np.finfo(float).tiny:raise ConvergenceFailure('BiCGSTAB rho breakdown')
        beta=(rho1/rho)*(alpha/omega);p=r+beta*(p-omega*v);v=A.matvec(p);den=float(rh@v)
        if abs(den)<np.finfo(float).tiny:raise ConvergenceFailure('BiCGSTAB alpha breakdown')
        alpha=rho1/den;s=r-alpha*v
        if np.linalg.norm(s)<=tol*(np.linalg.norm(b)+1):x+=alpha*p;return SolverResult(x,True,k,float(np.linalg.norm(s)),'tolerance',time.perf_counter()-t,history=hist)
        tt=A.matvec(s);den2=float(tt@tt)
        if den2==0:raise ConvergenceFailure('BiCGSTAB omega breakdown')
        omega=float(tt@s)/den2;x+=alpha*p+omega*s;r=s-omega*tt;rn=float(np.linalg.norm(r));hist.append(rn)
        if rn<=tol*(np.linalg.norm(b)+1):return SolverResult(x,True,k,rn,'tolerance',time.perf_counter()-t,history=hist)
        if abs(omega)<np.finfo(float).tiny:raise ConvergenceFailure('BiCGSTAB omega zero')
        rho=rho1
    return SolverResult(x,False,max_iter,hist[-1] if hist else float(np.linalg.norm(r)),'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')
