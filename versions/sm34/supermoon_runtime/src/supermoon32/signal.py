from __future__ import annotations
import numpy as np
from .core import *
def fft(x):return np.fft.fft(finite_array(x,'x',1))
def ifft(X):
    X=np.asarray(X,complex)
    if X.ndim!=1 or X.size==0:raise InvalidInput('1-D spectrum required')
    return np.fft.ifft(X)
def convolution(x,h,mode='full'):return np.convolve(finite_array(x,'x',1),finite_array(h,'h',1),mode=mode)
def correlation(x,y,mode='full'):return np.correlate(finite_array(x,'x',1),finite_array(y,'y',1),mode=mode)
def parseval_error(x):
    x=finite_array(x,'x',1);X=np.fft.fft(x);return float(abs(np.sum(np.abs(x)**2)-np.sum(np.abs(X)**2)/len(x)))
def lowpass_fft(x,sample_rate,cutoff):
    x=finite_array(x,'x',1);sr=float(sample_rate);cut=float(cutoff)
    if sr<=0 or not 0<=cut<=sr/2:raise InvalidInput('invalid frequencies')
    X=np.fft.rfft(x);f=np.fft.rfftfreq(len(x),1/sr);X[f>cut]=0;return np.fft.irfft(X,n=len(x))
