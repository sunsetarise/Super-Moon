from __future__ import annotations
from dataclasses import dataclass
import numpy as np, math
from .core import *
def softmax(x,axis=-1):
    x=np.asarray(x,float)
    if x.size==0 or np.any(np.isnan(x)) or np.any(np.isposinf(x)): raise InvalidInput('softmax input contains invalid values')
    m=np.max(x,axis=axis,keepdims=True)
    if np.any(~np.isfinite(m)): raise InvalidInput('softmax row has no finite entries')
    e=np.exp(x-m);return e/np.sum(e,axis=axis,keepdims=True)
def attention(Q,K,V,mask=None):
    Q=finite_array(Q,'Q');K=finite_array(K,'K');V=finite_array(V,'V')
    if Q.ndim!=2 or K.ndim!=2 or V.ndim!=2 or Q.shape[1]!=K.shape[1] or K.shape[0]!=V.shape[0]:raise DimensionMismatch('attention shape mismatch')
    scores=Q@K.T/math.sqrt(Q.shape[1])
    if mask is not None:
        m=np.asarray(mask,bool)
        if m.shape!=scores.shape:raise DimensionMismatch('mask shape mismatch')
        scores=np.where(m,scores,-np.inf)
        if np.any(np.all(~m,axis=1)):raise InvalidInput('fully masked query row')
    W=softmax(scores,axis=1);return W@V,W
@dataclass
class Dense:
    W: np.ndarray; b: np.ndarray
    @classmethod
    def init(cls,in_dim,out_dim,seed=0):
        rng=np.random.default_rng(seed);W=rng.normal(scale=math.sqrt(2/(in_dim+out_dim)),size=(in_dim,out_dim));return cls(W,np.zeros(out_dim))
    def forward(self,x):
        x=finite_array(x,'x');return x@self.W+self.b

def relu(x):return np.maximum(np.asarray(x,float),0.)
def mse(yhat,y):
    yhat=np.asarray(yhat,float);y=np.asarray(y,float);return float(np.mean((yhat-y)**2))
def numerical_gradient(f,x,eps=1e-6):
    x=np.asarray(x,float).copy();g=np.empty_like(x)
    it=np.nditer(x,flags=['multi_index'])
    while not it.finished:
        i=it.multi_index;old=x[i];x[i]=old+eps;fp=f(x);x[i]=old-eps;fm=f(x);x[i]=old;g[i]=(fp-fm)/(2*eps);it.iternext()
    return g
def linear_regression_train(X,y,lr=.05,epochs=1000,tol=1e-10):
    X=finite_array(X,'X',2);y=finite_array(y,'y',1)
    if len(X)!=len(y):raise DimensionMismatch('X/y mismatch')
    w=np.zeros(X.shape[1]);b=0.;hist=[]
    for k in range(int(epochs)):
        pred=X@w+b;err=pred-y;loss=float(np.mean(err*err));hist.append(loss);gw=2*X.T@err/len(y);gb=2*np.mean(err);w-=lr*gw;b-=lr*gb
        if np.linalg.norm(np.r_[gw,gb])<=tol:break
    return {'weights':w,'bias':float(b),'loss':hist[-1],'history':hist,'epochs':len(hist)}
def cosine_beta_schedule(T,s=0.008):
    T=int(T)
    if T<=0:raise InvalidInput('T positive')
    t=np.linspace(0,T,T+1)/T;abar=np.cos((t+s)/(1+s)*np.pi/2)**2;abar/=abar[0];beta=1-abar[1:]/abar[:-1];return np.clip(beta,1e-8,.999)
def q_learning_step(Q,s,a,r,s2,alpha=.1,gamma=.99):
    Q=np.asarray(Q,float);target=float(r)+gamma*np.max(Q[s2]);td=target-Q[s,a];Q[s,a]+=alpha*td;return float(td)
