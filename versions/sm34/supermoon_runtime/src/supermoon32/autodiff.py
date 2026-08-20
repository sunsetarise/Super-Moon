from __future__ import annotations
from dataclasses import dataclass
import math,numpy as np
from .core import *
@dataclass
class Dual:
    val: float; der: float=0.0
    def __add__(self,o):o=o if isinstance(o,Dual) else Dual(float(o));return Dual(self.val+o.val,self.der+o.der)
    __radd__=__add__
    def __sub__(self,o):o=o if isinstance(o,Dual) else Dual(float(o));return Dual(self.val-o.val,self.der-o.der)
    def __rsub__(self,o):return Dual(float(o)).__sub__(self)
    def __mul__(self,o):o=o if isinstance(o,Dual) else Dual(float(o));return Dual(self.val*o.val,self.der*o.val+self.val*o.der)
    __rmul__=__mul__
    def __truediv__(self,o):o=o if isinstance(o,Dual) else Dual(float(o));return Dual(self.val/o.val,(self.der*o.val-self.val*o.der)/(o.val*o.val))
    def __rtruediv__(self,o):return Dual(float(o)).__truediv__(self)
    def __pow__(self,p):p=float(p);return Dual(self.val**p,p*self.val**(p-1)*self.der)
    def __neg__(self):return Dual(-self.val,-self.der)
def sin(x):return Dual(math.sin(x.val),math.cos(x.val)*x.der) if isinstance(x,Dual) else math.sin(x)
def cos(x):return Dual(math.cos(x.val),-math.sin(x.val)*x.der) if isinstance(x,Dual) else math.cos(x)
def exp(x):return Dual(math.exp(x.val),math.exp(x.val)*x.der) if isinstance(x,Dual) else math.exp(x)
def log(x):return Dual(math.log(x.val),x.der/x.val) if isinstance(x,Dual) else math.log(x)
def derivative(f,x):return float(f(Dual(float(x),1.)).der)
def jvp(f,x,v,eps=None):
    x=finite_array(x,'x',1);v=finite_array(v,'v',1)
    if x.shape!=v.shape:raise DimensionMismatch('x/v mismatch')
    eps=np.sqrt(np.finfo(float).eps)*(1+np.linalg.norm(x))/max(np.linalg.norm(v),np.finfo(float).tiny) if eps is None else float(eps);return (np.asarray(f(x+eps*v),float)-np.asarray(f(x-eps*v),float))/(2*eps)
def vjp(f,x,w,eps=None):
    x=finite_array(x,'x',1);w=finite_array(w,'w',1);eps=np.sqrt(np.finfo(float).eps) if eps is None else float(eps);g=np.empty_like(x)
    for i in range(len(x)):
        h=eps*max(1.,abs(x[i]));xp=x.copy();xm=x.copy();xp[i]+=h;xm[i]-=h;g[i]=w@(np.asarray(f(xp),float)-np.asarray(f(xm),float))/(2*h)
    return g
