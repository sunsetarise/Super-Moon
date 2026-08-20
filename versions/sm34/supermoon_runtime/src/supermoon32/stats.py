from __future__ import annotations
import numpy as np
from .core import *
def mean(x):
    a=finite_array(x,'x',1);return kahan_sum(a)/len(a)
def variance(x,ddof=1):
    a=finite_array(x,'x',1);m=mean(a)
    if len(a)<=ddof:raise InvalidInput('insufficient samples')
    return kahan_sum((float(v)-m)**2 for v in a)/(len(a)-ddof)
def covariance(x,y,ddof=1):
    x=finite_array(x,'x',1);y=finite_array(y,'y',1)
    if len(x)!=len(y) or len(x)<=ddof:raise DimensionMismatch('sample mismatch')
    mx,my=mean(x),mean(y);return kahan_sum((float(a)-mx)*(float(b)-my) for a,b in zip(x,y))/(len(x)-ddof)
def correlation(x,y):return covariance(x,y)/(variance(x)**.5*variance(y)**.5)
def median(x):return float(np.median(finite_array(x,'x',1)))
def mad(x,scale=1.4826):
    a=finite_array(x,'x',1);m=np.median(a);return float(scale*np.median(np.abs(a-m)))
def quantile(x,q):return float(np.quantile(finite_array(x,'x',1),q))
