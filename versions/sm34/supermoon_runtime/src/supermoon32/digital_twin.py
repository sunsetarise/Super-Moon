from __future__ import annotations
from dataclasses import dataclass,field
import time, numpy as np
from .core import *
@dataclass
class StateTwin:
    state: np.ndarray; covariance: np.ndarray; parameters: dict=field(default_factory=dict); history:list=field(default_factory=list); provenance:dict=field(default_factory=dict)
    def __post_init__(self):
        self.state=finite_array(self.state,'state',1);self.covariance=finite_array(self.covariance,'covariance',2)
        if self.covariance.shape!=(len(self.state),len(self.state)):raise DimensionMismatch('covariance dimension mismatch')
        if np.min(np.linalg.eigvalsh((self.covariance+self.covariance.T)/2))<-1e-12:raise InvalidInput('covariance must be PSD')
    def predict(self,F,Q=None,control=None,B=None,timestamp=None):
        F=finite_array(F,'F',2);Q=np.zeros_like(self.covariance) if Q is None else finite_array(Q,'Q',2);x=F@self.state
        if control is not None:
            if B is None:raise InvalidInput('B required with control')
            x=x+np.asarray(B,float)@np.asarray(control,float)
        self.state=x;self.covariance=F@self.covariance@F.T+Q;self.history.append({'kind':'predict','timestamp':time.time() if timestamp is None else timestamp,'state':self.state.copy()});return self.state.copy()
    def update(self,z,H,R,timestamp=None):
        z=finite_array(z,'z',1);H=finite_array(H,'H',2);R=finite_array(R,'R',2);innovation=z-H@self.state;S=H@self.covariance@H.T+R
        try:K=np.linalg.solve(S,(self.covariance@H.T).T).T
        except np.linalg.LinAlgError as e:raise SingularSystem('innovation covariance singular') from e
        self.state=self.state+K@innovation;I=np.eye(len(self.state));self.covariance=(I-K@H)@self.covariance@(I-K@H).T+K@R@K.T;self.history.append({'kind':'update','timestamp':time.time() if timestamp is None else timestamp,'innovation':innovation.copy(),'state':self.state.copy()});return {'state':self.state.copy(),'innovation':innovation,'innovation_norm':float(np.linalg.norm(innovation))}
