from __future__ import annotations
import time, numpy as np
from .core import *

def _fd_grad(f,x,eps=None):
    x=np.asarray(x,float);g=np.empty_like(x);eps=np.sqrt(np.finfo(float).eps) if eps is None else float(eps)
    for i in range(len(x)):
        h=eps*max(1.,abs(x[i]));xp=x.copy();xm=x.copy();xp[i]+=h;xm[i]-=h;g[i]=(float(f(xp))-float(f(xm)))/(2*h)
    return g

def gradient_descent(f,x0,grad=None,lr=1e-2,tol=1e-8,max_iter=1000,momentum=0.0):
    x=finite_array(x0,'x0',1).copy();v=np.zeros_like(x);hist=[];evals=0;gevals=0;t=time.perf_counter()
    for k in range(max_iter+1):
        fx=float(f(x));evals+=1;g=_fd_grad(f,x) if grad is None else finite_array(grad(x),'grad',1);gevals+=1;gn=float(np.linalg.norm(g));hist.append(fx)
        if gn<=tol:return SolverResult(x,True,k,gn,'gradient_tolerance',time.perf_counter()-t,{'objective':fx,'objective_evals':evals,'gradient_evals':gevals},hist)
        if k==max_iter:break
        v=momentum*v+g; step=-lr*v; alpha=1.0
        while alpha>1e-8 and float(f(x+alpha*step))>fx-1e-4*alpha*lr*gn*gn: alpha*=0.5;evals+=1
        x=x+alpha*step
    return SolverResult(x,False,max_iter,gn,'max_iter',time.perf_counter()-t,{'objective':fx,'objective_evals':evals,'gradient_evals':gevals},hist,status='NOT_CONVERGED')

def bfgs(f,x0,grad=None,tol=1e-8,max_iter=200):
    x=finite_array(x0,'x0',1).copy();n=len(x);H=np.eye(n);hist=[];evals=gevals=0;t=time.perf_counter();g=_fd_grad(f,x) if grad is None else np.asarray(grad(x),float);gevals+=1
    for k in range(max_iter+1):
        fx=float(f(x));evals+=1;gn=float(np.linalg.norm(g));hist.append(fx)
        if gn<=tol:return SolverResult(x,True,k,gn,'gradient_tolerance',time.perf_counter()-t,{'objective':fx,'objective_evals':evals,'gradient_evals':gevals},hist)
        if k==max_iter:break
        p=-H@g;alpha=1.0
        while alpha>1e-10:
            xn=x+alpha*p;fn=float(f(xn));evals+=1
            if fn<=fx+1e-4*alpha*float(g@p):break
            alpha*=.5
        s=alpha*p;xn=x+s;gnext=_fd_grad(f,xn) if grad is None else np.asarray(grad(xn),float);gevals+=1;y=gnext-g;ys=float(y@s)
        if ys>1e-14:
            rho=1/ys;I=np.eye(n);H=(I-rho*np.outer(s,y))@H@(I-rho*np.outer(y,s))+rho*np.outer(s,s)
        x,g=xn,gnext
    return SolverResult(x,False,max_iter,float(np.linalg.norm(g)),'max_iter',time.perf_counter()-t,{'objective':float(f(x)),'objective_evals':evals+1,'gradient_evals':gevals},hist,status='NOT_CONVERGED')

def lbfgs(f,x0,grad=None,tol=1e-8,max_iter=300,memory=10):
    x=finite_array(x0,'x0',1).copy();S=[];Y=[];R=[];hist=[];evals=gevals=0;t=time.perf_counter();g=_fd_grad(f,x) if grad is None else np.asarray(grad(x),float);gevals+=1
    for k in range(max_iter+1):
        fx=float(f(x));evals+=1;gn=float(np.linalg.norm(g));hist.append(fx)
        if gn<=tol:return SolverResult(x,True,k,gn,'gradient_tolerance',time.perf_counter()-t,{'objective':fx,'objective_evals':evals,'gradient_evals':gevals},hist)
        q=g.copy();alpha=[]
        for s,y,r in reversed(list(zip(S,Y,R))):a=r*(s@q);alpha.append(a);q-=a*y
        gamma=(S[-1]@Y[-1])/(Y[-1]@Y[-1]) if S else 1.0;z=gamma*q
        for (s,y,r),a in zip(zip(S,Y,R),reversed(alpha)):z+=s*(a-r*(y@z))
        p=-z;step=1.0
        while step>1e-10 and float(f(x+step*p))>fx+1e-4*step*(g@p):step*=.5;evals+=1
        xn=x+step*p;gnext=_fd_grad(f,xn) if grad is None else np.asarray(grad(xn),float);gevals+=1;s=xn-x;y=gnext-g;ys=float(y@s)
        if ys>1e-14:
            if len(S)==memory:S.pop(0);Y.pop(0);R.pop(0)
            S.append(s);Y.append(y);R.append(1/ys)
        x,g=xn,gnext
    return SolverResult(x,False,max_iter,float(np.linalg.norm(g)),'max_iter',time.perf_counter()-t,{'objective':float(f(x)),'objective_evals':evals+1,'gradient_evals':gevals},hist,status='NOT_CONVERGED')

def projected_gradient(f,x0,bounds,grad=None,lr=.05,tol=1e-8,max_iter=500):
    x=np.asarray(x0,float).copy();lo=np.array([b[0] for b in bounds],float);hi=np.array([b[1] for b in bounds],float)
    if len(x)!=len(lo) or np.any(lo>hi):raise InvalidInput('invalid bounds')
    hist=[];t=time.perf_counter()
    for k in range(max_iter+1):
        g=_fd_grad(f,x) if grad is None else np.asarray(grad(x),float);xn=np.clip(x-lr*g,lo,hi);pg=x-xn;hist.append(float(f(x)))
        if np.linalg.norm(pg)<=tol:return SolverResult(x,True,k,float(np.linalg.norm(pg)),'projected_gradient_tolerance',time.perf_counter()-t,{'objective':float(f(x)),'constraint_violation':0.0},hist)
        x=xn
    return SolverResult(x,False,max_iter,float(np.linalg.norm(pg)),'max_iter',time.perf_counter()-t,{'objective':float(f(x)),'constraint_violation':0.0},hist,status='NOT_CONVERGED')

def constraint_violation(x,ineq=(),eq=()):
    return float(sum(max(0.,float(g(x))) for g in ineq)+sum(abs(float(h(x))) for h in eq))

def penalty_optimize(f,x0,ineq=(),eq=(),penalty=1e4,**kwargs):
    obj=lambda x:float(f(x))+penalty*constraint_violation(x,ineq,eq)**2
    r=bfgs(obj,x0,**kwargs);r.diagnostics['constraint_violation']=constraint_violation(r.solution,ineq,eq);r.diagnostics['original_objective']=float(f(r.solution));return r

def nelder_mead(f,x0,step=.1,tol=1e-8,max_iter=1000):
    x0=finite_array(x0,'x0',1);n=len(x0);simplex=np.vstack([x0]+[x0+step*np.eye(n)[i] for i in range(n)]);vals=np.array([f(x) for x in simplex],float);hist=[];t=time.perf_counter()
    for k in range(max_iter+1):
        idx=np.argsort(vals);simplex=simplex[idx];vals=vals[idx];hist.append(float(vals[0]))
        if np.std(vals)<=tol:return SolverResult(simplex[0],True,k,float(np.std(vals)),'simplex_tolerance',time.perf_counter()-t,{'objective':float(vals[0])},hist)
        c=np.mean(simplex[:-1],axis=0);xr=c+(c-simplex[-1]);fr=float(f(xr))
        if vals[0]<=fr<vals[-2]:simplex[-1],vals[-1]=xr,fr;continue
        if fr<vals[0]:
            xe=c+2*(xr-c);fe=float(f(xe));simplex[-1],vals[-1]=(xe,fe) if fe<fr else (xr,fr);continue
        xc=c+.5*(simplex[-1]-c);fc=float(f(xc))
        if fc<vals[-1]:simplex[-1],vals[-1]=xc,fc;continue
        simplex[1:]=simplex[0]+.5*(simplex[1:]-simplex[0]);vals[1:]=[f(x) for x in simplex[1:]]
    return SolverResult(simplex[0],False,max_iter,float(np.std(vals)),'max_iter',time.perf_counter()-t,{'objective':float(vals[0])},hist,status='NOT_CONVERGED')
