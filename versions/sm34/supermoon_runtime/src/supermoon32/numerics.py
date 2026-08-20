from __future__ import annotations
import math,time
import numpy as np
from .core import *

def lu_factor(A,pivot_tol=1e-15):
    A=finite_array(A,'A',2).copy(); n,m=A.shape
    if n!=m: raise DimensionMismatch('A must be square')
    P=np.arange(n)
    for k in range(n-1):
        p=k+int(np.argmax(np.abs(A[k:,k])))
        if abs(A[p,k]) <= pivot_tol*max(1.0,float(np.linalg.norm(A,np.inf))): raise SingularSystem('singular pivot')
        if p!=k: A[[k,p]]=A[[p,k]];P[[k,p]]=P[[p,k]]
        A[k+1:,k]/=A[k,k]; A[k+1:,k+1:]-=np.outer(A[k+1:,k],A[k,k+1:])
    if abs(A[-1,-1]) <= pivot_tol*max(1.0,float(np.linalg.norm(A,np.inf))): raise SingularSystem('singular pivot')
    return P,np.tril(A,-1)+np.eye(n),np.triu(A)

def forward_substitution(L,b):
    L=finite_array(L,'L',2); b=finite_array(b,'b')
    n=L.shape[0]; y=np.zeros_like(b,dtype=float)
    for i in range(n): y[i]=(b[i]-L[i,:i]@y[:i])/L[i,i]
    return y

def backward_substitution(U,b):
    U=finite_array(U,'U',2); b=finite_array(b,'b'); n=U.shape[0];x=np.zeros_like(b,dtype=float)
    for i in range(n-1,-1,-1):
        if abs(U[i,i])<np.finfo(float).tiny: raise SingularSystem('zero diagonal')
        x[i]=(b[i]-U[i,i+1:]@x[i+1:])/U[i,i]
    return x

def lu_solve(A,b):
    P,L,U=lu_factor(A); bb=finite_array(b,'b'); y=forward_substitution(L,bb[P]); return backward_substitution(U,y)

def qr_householder(A):
    A=finite_array(A,'A',2).copy(); m,n=A.shape; Q=np.eye(m);R=A
    for k in range(min(m,n)):
        x=R[k:,k]; norm=np.linalg.norm(x)
        if norm==0: continue
        alpha=-math.copysign(norm,x[0] if x[0]!=0 else 1.0); v=x.copy();v[0]-=alpha;vn=np.linalg.norm(v)
        if vn==0:continue
        v/=vn; R[k:]-=2*np.outer(v,v@R[k:]); Q[:,k:]-=2*np.outer(Q[:,k:]@v,v)
    R[np.abs(R)<1e-15]=0.0; return Q,R

def cholesky(A,tol=1e-14):
    A=finite_array(A,'A',2); n,m=A.shape
    if n!=m or not np.allclose(A,A.T,rtol=1e-10,atol=1e-12): raise InvalidInput('A must be symmetric square')
    L=np.zeros_like(A)
    for i in range(n):
        for j in range(i+1):
            s=A[i,j]-np.dot(L[i,:j],L[j,:j])
            if i==j:
                if s<=tol: raise InvalidInput('A is not positive definite')
                L[i,j]=math.sqrt(s)
            else:L[i,j]=s/L[j,j]
    return L

def svd(A): return np.linalg.svd(finite_array(A,'A',2),full_matrices=False)
def eig(A): return np.linalg.eig(finite_array(A,'A',2))
def least_squares(A,b,rcond=None): return np.linalg.lstsq(finite_array(A,'A',2),finite_array(b,'b'),rcond=rcond)
def pseudoinverse(A,rcond=1e-12):
    U,s,Vt=svd(A); cutoff=rcond*(s[0] if len(s) else 1.0); si=np.where(s>cutoff,1/s,0); return (Vt.T*si)@U.T

def condition_estimate(A):
    A=finite_array(A,'A',2); return float(np.linalg.cond(A))

def iterative_refinement(A,b,x0=None,tol=1e-12,max_iter=10):
    A=finite_array(A,'A',2);b=finite_array(b,'b');x=lu_solve(A,b) if x0 is None else finite_array(x0,'x0').copy(); hist=[];t=time.perf_counter()
    for k in range(max_iter+1):
        r=b-A@x; rn=float(np.linalg.norm(r));hist.append(rn)
        if rn<=tol*(np.linalg.norm(b)+1): return SolverResult(x,True,k,rn,'tolerance',time.perf_counter()-t,history=hist)
        if k==max_iter:break
        x+=lu_solve(A,r)
    return SolverResult(x,False,max_iter,hist[-1],'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')

def bisection(f,a,b,tol=1e-12,max_iter=200):
    a=finite_scalar(a);b=finite_scalar(b);fa=float(f(a));fb=float(f(b));t=time.perf_counter();hist=[]
    if not all(map(math.isfinite,[fa,fb])): raise InvalidInput('non-finite function value')
    if fa==0:return SolverResult(a,True,0,0,'exact_endpoint')
    if fb==0:return SolverResult(b,True,0,0,'exact_endpoint')
    if fa*fb>0: raise InvalidInput('root not bracketed')
    for k in range(1,max_iter+1):
        c=(a+b)/2;fc=float(f(c)); hist.append(abs(fc))
        if not math.isfinite(fc): raise InvalidInput('function produced NaN/Inf')
        if abs(fc)<=tol or abs(b-a)<=tol*(1+abs(c)): return SolverResult(c,True,k,abs(fc),'tolerance',time.perf_counter()-t,history=hist)
        if fa*fc<=0:b,fb=c,fc
        else:a,fa=c,fc
    return SolverResult(c,False,max_iter,abs(fc),'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')

def secant(f,x0,x1,tol=1e-12,max_iter=100):
    x0=float(x0);x1=float(x1);f0=float(f(x0));f1=float(f(x1));hist=[];t=time.perf_counter()
    for k in range(1,max_iter+1):
        den=f1-f0
        if abs(den)<=np.finfo(float).eps*max(1,abs(f0),abs(f1)): raise ConvergenceFailure('secant denominator collapsed')
        x2=x1-f1*(x1-x0)/den;f2=float(f(x2));hist.append(abs(f2))
        if not math.isfinite(f2): raise InvalidInput('function produced NaN/Inf')
        if abs(f2)<=tol:return SolverResult(x2,True,k,abs(f2),'tolerance',time.perf_counter()-t,history=hist)
        x0,f0,x1,f1=x1,f1,x2,f2
    return SolverResult(x1,False,max_iter,abs(f1),'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')

def newton_scalar(f,df,x0,tol=1e-12,max_iter=100,damping=True):
    x=float(x0);hist=[];t=time.perf_counter()
    for k in range(max_iter+1):
        fx=float(f(x));hist.append(abs(fx))
        if not math.isfinite(fx):raise InvalidInput('function produced NaN/Inf')
        if abs(fx)<=tol:return SolverResult(x,True,k,abs(fx),'tolerance',time.perf_counter()-t,history=hist)
        if k==max_iter:break
        d=float(df(x))
        if not math.isfinite(d) or abs(d)<=np.finfo(float).eps:raise ConvergenceFailure('zero/nonfinite derivative')
        step=-fx/d; alpha=1.0
        if damping:
            while alpha>1e-8:
                fn=float(f(x+alpha*step))
                if math.isfinite(fn) and abs(fn)<abs(fx):break
                alpha*=0.5
        x+=alpha*step
    return SolverResult(x,False,max_iter,hist[-1],'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')

def brent(f,a,b,tol=1e-12,max_iter=100):
    # Safeguarded secant/bisection hybrid.
    a=float(a);b=float(b);fa=float(f(a));fb=float(f(b));
    if fa*fb>0:raise InvalidInput('root not bracketed')
    hist=[];t=time.perf_counter()
    for k in range(1,max_iter+1):
        if abs(fb-fa)>np.finfo(float).eps:maxsec=b-fb*(b-a)/(fb-fa)
        else:maxsec=(a+b)/2
        lo,hi=min(a,b),max(a,b)
        c=maxsec if lo < maxsec < hi else (a+b)/2
        fc=float(f(c));hist.append(abs(fc))
        if abs(fc)<=tol or abs(b-a)<=tol*(1+abs(c)):return SolverResult(c,True,k,abs(fc),'tolerance',time.perf_counter()-t,history=hist)
        if fa*fc<=0:b,fb=c,fc
        else:a,fa=c,fc
    return SolverResult(c,False,max_iter,abs(fc),'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')

def finite_difference_jacobian(F,x,eps=None):
    x=finite_array(x,'x',1);f0=finite_array(F(x),'F(x)',1);J=np.empty((len(f0),len(x))); eps=math.sqrt(np.finfo(float).eps) if eps is None else float(eps)
    for j in range(len(x)):
        h=eps*max(1.0,abs(x[j]));xp=x.copy();xm=x.copy();xp[j]+=h;xm[j]-=h;J[:,j]=(finite_array(F(xp),'F+',1)-finite_array(F(xm),'F-',1))/(2*h)
    return J

def newton_system(F,x0,jac=None,tol=1e-10,max_iter=50):
    x=finite_array(x0,'x0',1).copy();hist=[];t=time.perf_counter()
    for k in range(max_iter+1):
        f=finite_array(F(x),'F',1);rn=float(np.linalg.norm(f));hist.append(rn)
        if rn<=tol:return SolverResult(x,True,k,rn,'tolerance',time.perf_counter()-t,history=hist)
        if k==max_iter:break
        J=finite_difference_jacobian(F,x) if jac is None else finite_array(jac(x),'J',2)
        try:step=np.linalg.solve(J,-f)
        except np.linalg.LinAlgError as e:raise SingularSystem('singular Jacobian') from e
        alpha=1.0
        while alpha>1e-8 and np.linalg.norm(F(x+alpha*step))>=rn:alpha*=0.5
        x=x+alpha*step
    return SolverResult(x,False,max_iter,hist[-1],'max_iter',time.perf_counter()-t,history=hist,status='NOT_CONVERGED')
