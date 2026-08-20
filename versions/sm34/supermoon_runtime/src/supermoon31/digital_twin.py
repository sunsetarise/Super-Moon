from __future__ import annotations
from dataclasses import dataclass,field
import numpy as np
@dataclass
class KalmanTwin:
    x:np.ndarray; P:np.ndarray; F:np.ndarray; H:np.ndarray; Q:np.ndarray; R:np.ndarray; history:list=field(default_factory=list)
    def predict(self,u=None,B=None): self.x=self.F@self.x+(0 if u is None else B@u);self.P=self.F@self.P@self.F.T+self.Q;return self.x
    def update(self,y):
        y=np.asarray(y,float);S=self.H@self.P@self.H.T+self.R;K=self.P@self.H.T@np.linalg.inv(S);innov=y-self.H@self.x;self.x=self.x+K@innov;I=np.eye(len(self.x));self.P=(I-K@self.H)@self.P@(I-K@self.H).T+K@self.R@K.T;self.history.append({'innovation_norm':float(np.linalg.norm(innov))});return self.x


# ================= CELESTIAL DEPTH: Kalman state/covariance stability =================
def _kalman_validate(self):
    self.x=np.asarray(self.x,float);self.P=np.asarray(self.P,float);self.F=np.asarray(self.F,float);self.H=np.asarray(self.H,float);self.Q=np.asarray(self.Q,float);self.R=np.asarray(self.R,float)
    n=self.x.size
    if self.x.ndim!=1 or self.P.shape!=(n,n) or self.F.shape!=(n,n) or self.Q.shape!=(n,n): raise ValueError('state/F/P/Q dimensions are inconsistent')
    if self.H.ndim!=2 or self.H.shape[1]!=n or self.R.shape!=(self.H.shape[0],self.H.shape[0]): raise ValueError('H/R dimensions are inconsistent')
    if not all(np.all(np.isfinite(a)) for a in (self.x,self.P,self.F,self.H,self.Q,self.R)): raise ValueError('Kalman matrices contain NaN/Inf')
    self.P=.5*(self.P+self.P.T);self.Q=.5*(self.Q+self.Q.T);self.R=.5*(self.R+self.R.T)
    if np.min(np.linalg.eigvalsh(self.P))<-1e-10 or np.min(np.linalg.eigvalsh(self.Q))<-1e-10 or np.min(np.linalg.eigvalsh(self.R))<-1e-10: raise ValueError('P/Q/R must be positive semidefinite within tolerance')
    return n

def _celestial_predict(self,u=None,B=None):
    _kalman_validate(self)
    if (u is None)!=(B is None): raise ValueError('u and B must be supplied together')
    control=0.0
    if u is not None:
        B=np.asarray(B,float);u=np.asarray(u,float)
        if B.ndim!=2 or B.shape[0]!=len(self.x) or u.ndim!=1 or B.shape[1]!=len(u): raise ValueError('B/u dimensions are inconsistent')
        if not np.all(np.isfinite(B)) or not np.all(np.isfinite(u)): raise ValueError('B/u contain NaN/Inf')
        control=B@u
    self.x=self.F@self.x+control;self.P=self.F@self.P@self.F.T+self.Q;self.P=.5*(self.P+self.P.T)
    return self.x

def _celestial_update(self,y):
    _kalman_validate(self);y=np.asarray(y,float)
    if y.shape!=(self.H.shape[0],) or not np.all(np.isfinite(y)): raise ValueError('measurement dimension/values invalid')
    S=self.H@self.P@self.H.T+self.R;S=.5*(S+S.T)
    if np.min(np.linalg.eigvalsh(S))<=np.finfo(float).eps: raise np.linalg.LinAlgError('NUMERICAL_BREAKDOWN: innovation covariance not positive definite')
    PHt=self.P@self.H.T
    K=np.linalg.solve(S.T,PHt.T).T
    innov=y-self.H@self.x;self.x=self.x+K@innov;I=np.eye(len(self.x));self.P=(I-K@self.H)@self.P@(I-K@self.H).T+K@self.R@K.T;self.P=.5*(self.P+self.P.T)
    nis=float(innov@np.linalg.solve(S,innov))
    self.history.append({'innovation_norm':float(np.linalg.norm(innov)),'normalized_innovation_squared':nis,'condition_S':float(np.linalg.cond(S))})
    return self.x

KalmanTwin.predict=_celestial_predict
KalmanTwin.update=_celestial_update
