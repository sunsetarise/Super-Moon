from __future__ import annotations
from dataclasses import dataclass
import math,numpy as np
from ..core import InvalidInput

@dataclass
class PolynomialSurrogate:
    coefficients:np.ndarray; powers:list[tuple[int,...]]; dimension:int; training_bounds:np.ndarray; rmse:float
    def predict(self,X):
        X=np.atleast_2d(np.asarray(X,float));Phi=np.column_stack([np.prod(X**np.array(p),axis=1) for p in self.powers]);y=Phi@self.coefficients;return y if len(y)>1 else float(y[0])
    def inside_domain(self,x):
        x=np.asarray(x,float);return bool(np.all((x>=self.training_bounds[:,0])&(x<=self.training_bounds[:,1])))

def _powers(d,degree):
    import itertools
    return [p for p in itertools.product(range(degree+1),repeat=d) if sum(p)<=degree]

def fit_polynomial_surrogate(X,y,degree=2):
    X=np.asarray(X,float);y=np.asarray(y,float)
    if X.ndim!=2 or y.ndim!=1 or len(X)!=len(y) or len(X)==0:raise InvalidInput('X must be (n,d), y must be (n,)')
    p=_powers(X.shape[1],int(degree));Phi=np.column_stack([np.prod(X**np.array(q),axis=1) for q in p]);coef,*_=np.linalg.lstsq(Phi,y,rcond=None);pred=Phi@coef;rmse=float(np.sqrt(np.mean((pred-y)**2)));bounds=np.column_stack((X.min(0),X.max(0)));return PolynomialSurrogate(coef,p,X.shape[1],bounds,rmse)

@dataclass
class RBFModel:
    centers:np.ndarray; weights:np.ndarray; epsilon:float; training_bounds:np.ndarray; rmse:float
    def predict(self,X):
        X=np.atleast_2d(np.asarray(X,float));D=np.linalg.norm(X[:,None,:]-self.centers[None,:,:],axis=2);Phi=np.exp(-(self.epsilon*D)**2);y=Phi@self.weights;return y if len(y)>1 else float(y[0])

def fit_rbf(X,y,epsilon=1.0,regularization=1e-10):
    X=np.asarray(X,float);y=np.asarray(y,float)
    if X.ndim!=2 or y.shape!=(len(X),) or len(X)<2:raise InvalidInput('valid X/y with at least 2 samples required')
    D=np.linalg.norm(X[:,None,:]-X[None,:,:],axis=2);Phi=np.exp(-(float(epsilon)*D)**2);w=np.linalg.solve(Phi+regularization*np.eye(len(X)),y);pred=Phi@w;return RBFModel(X,w,float(epsilon),np.column_stack((X.min(0),X.max(0))),float(np.sqrt(np.mean((pred-y)**2))))

def multifidelity_linear(low,high):
    l=np.asarray(low,float);h=np.asarray(high,float)
    if l.shape!=h.shape or l.size<2:raise InvalidInput('low/high fidelity arrays must share shape and contain >=2 values')
    A=np.column_stack((l,np.ones(l.size)));rho,delta=np.linalg.lstsq(A,h,rcond=None)[0];pred=rho*l+delta;return {'rho':float(rho),'delta':float(delta),'rmse':float(np.sqrt(np.mean((pred-h)**2))),'predict':lambda x:rho*np.asarray(x)+delta}

def select_max_uncertainty(points,uncertainty):
    P=np.asarray(points,float);u=np.asarray(uncertainty,float)
    if P.ndim!=2 or u.shape!=(len(P),) or len(P)==0:raise InvalidInput('points/uncertainty shape mismatch')
    i=int(np.argmax(u));return {'index':i,'point':P[i].copy(),'uncertainty':float(u[i])}
