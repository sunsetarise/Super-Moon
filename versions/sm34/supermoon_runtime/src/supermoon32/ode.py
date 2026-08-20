from __future__ import annotations
from dataclasses import dataclass,field
import numpy as np, math
from .core import *
@dataclass
class ODEResult:
    t: np.ndarray; y: np.ndarray; accepted: int; rejected: int=0; events: list=field(default_factory=list)

def _prep(fun,t_span,y0,dt):
    t0,tf=map(float,t_span); y=finite_array(y0,'y0',1).copy();dt=float(dt)
    if tf<t0 or dt<=0:raise InvalidInput('require tf>=t0 and dt>0')
    return t0,tf,y,dt

def euler(fun,t_span,y0,dt):
    t,tf,y,dt=_prep(fun,t_span,y0,dt);ts=[t];ys=[y.copy()]
    while t<tf-1e-15:
        h=min(dt,tf-t);y=y+h*finite_array(fun(t,y),'f',1);t+=h;ts.append(t);ys.append(y.copy())
    return ODEResult(np.array(ts),np.array(ys),len(ts)-1)
def midpoint(fun,t_span,y0,dt):
    t,tf,y,dt=_prep(fun,t_span,y0,dt);ts=[t];ys=[y.copy()]
    while t<tf-1e-15:
        h=min(dt,tf-t);k1=finite_array(fun(t,y),'k1',1);k2=finite_array(fun(t+h/2,y+h*k1/2),'k2',1);y=y+h*k2;t+=h;ts.append(t);ys.append(y.copy())
    return ODEResult(np.array(ts),np.array(ys),len(ts)-1)
def rk4(fun,t_span,y0,dt):
    t,tf,y,dt=_prep(fun,t_span,y0,dt);ts=[t];ys=[y.copy()]
    while t<tf-1e-15:
        h=min(dt,tf-t);k1=np.asarray(fun(t,y),float);k2=np.asarray(fun(t+h/2,y+h*k1/2),float);k3=np.asarray(fun(t+h/2,y+h*k2/2),float);k4=np.asarray(fun(t+h,y+h*k3),float);y=y+h*(k1+2*k2+2*k3+k4)/6;t+=h
        if not np.all(np.isfinite(y)):raise NumericalOverflow('ODE produced NaN/Inf')
        ts.append(t);ys.append(y.copy())
    return ODEResult(np.array(ts),np.array(ys),len(ts)-1)
def rk45(fun,t_span,y0,dt=1e-2,rtol=1e-7,atol=1e-10,event=None,max_steps=100000):
    t,tf,y,h=_prep(fun,t_span,y0,dt);ts=[t];ys=[y.copy()];accepted=rejected=0;events=[];prev_event=float(event(t,y)) if event else None
    # Dormand-Prince 5(4)
    for _ in range(max_steps):
        if t>=tf-1e-15:break
        h=min(h,tf-t);k1=np.asarray(fun(t,y),float);k2=np.asarray(fun(t+h/5,y+h*k1/5),float);k3=np.asarray(fun(t+3*h/10,y+h*(3*k1/40+9*k2/40)),float);k4=np.asarray(fun(t+4*h/5,y+h*(44*k1/45-56*k2/15+32*k3/9)),float);k5=np.asarray(fun(t+8*h/9,y+h*(19372*k1/6561-25360*k2/2187+64448*k3/6561-212*k4/729)),float);k6=np.asarray(fun(t+h,y+h*(9017*k1/3168-355*k2/33+46732*k3/5247+49*k4/176-5103*k5/18656)),float);k7=np.asarray(fun(t+h,y+h*(35*k1/384+500*k3/1113+125*k4/192-2187*k5/6784+11*k6/84)),float)
        y5=y+h*(35*k1/384+500*k3/1113+125*k4/192-2187*k5/6784+11*k6/84);y4=y+h*(5179*k1/57600+7571*k3/16695+393*k4/640-92097*k5/339200+187*k6/2100+k7/40)
        scale=atol+rtol*np.maximum(np.abs(y),np.abs(y5));err=float(np.sqrt(np.mean(((y5-y4)/scale)**2)))
        if err<=1:
            told=t;t+=h;y=y5;accepted+=1;ts.append(t);ys.append(y.copy())
            if event:
                ev=float(event(t,y))
                if prev_event==0 or ev==0 or prev_event*ev<0:events.append({'t_left':told,'t_right':t,'value':ev})
                prev_event=ev
        else:rejected+=1
        fac=5.0 if err==0 else min(5.0,max(.2,.9*err**(-.2)));h*=fac
        if h<=np.finfo(float).tiny:raise ConvergenceFailure('adaptive step underflow')
    else:raise ConvergenceFailure('RK45 max steps exceeded')
    return ODEResult(np.array(ts),np.array(ys),accepted,rejected,events)
