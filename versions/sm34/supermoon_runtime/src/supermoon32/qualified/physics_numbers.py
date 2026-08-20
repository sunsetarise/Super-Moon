from __future__ import annotations
import math
from ..core import InvalidInput

def _positive(name,x,allow_zero=False):
    v=float(x)
    if (v<0 if allow_zero else v<=0):raise InvalidInput(f'{name} must be {"non-negative" if allow_zero else "positive"}')
    return v

def reynolds(rho,velocity,length,mu):return _positive('rho',rho)*abs(float(velocity))*_positive('length',length)/_positive('mu',mu)
def mach(velocity,speed_of_sound):return abs(float(velocity))/_positive('speed_of_sound',speed_of_sound)
def prandtl(cp,mu,k):return _positive('cp',cp)*_positive('mu',mu)/_positive('k',k)
def peclet(velocity,length,diffusivity):return abs(float(velocity))*_positive('length',length)/_positive('diffusivity',diffusivity)
def courant(velocity,dt,dx):return abs(float(velocity))*_positive('dt',dt,True)/_positive('dx',dx)
def froude(velocity,length,g=9.80665):return abs(float(velocity))/math.sqrt(_positive('g',g)*_positive('length',length))
def knudsen(mean_free_path,length):return _positive('mean_free_path',mean_free_path,True)/_positive('length',length)
def biot(h,length,k):return _positive('h',h)*_positive('length',length)/_positive('k',k)
def fourier(alpha,time,length):return _positive('alpha',alpha)*_positive('time',time,True)/(_positive('length',length)**2)
def strouhal(frequency,length,velocity):return _positive('frequency',frequency,True)*_positive('length',length)/max(abs(float(velocity)),1e-300)
def grashof(g,beta,delta_t,length,nu):return _positive('g',g)*_positive('beta',beta)*abs(float(delta_t))*_positive('length',length)**3/_positive('nu',nu)**2
def rayleigh(g,beta,delta_t,length,nu,alpha):return grashof(g,beta,delta_t,length,nu)*_positive('nu',nu)/_positive('alpha',alpha)
def weber(rho,velocity,length,surface_tension):return _positive('rho',rho)*float(velocity)**2*_positive('length',length)/_positive('surface_tension',surface_tension)

def nondimensional_summary(**kwargs):
    out={}
    specs={
        'Re':('rho','velocity','length','mu',reynolds),'Ma':('velocity','speed_of_sound',mach),'Pr':('cp','mu','k',prandtl),
        'Pe':('velocity','length','diffusivity',peclet),'Co':('velocity','dt','dx',courant),'Fr':('velocity','length',froude),
        'Kn':('mean_free_path','length',knudsen),'Bi':('h','length','k',biot),'Fo':('alpha','time','length',fourier),
        'St':('frequency','length','velocity',strouhal),'We':('rho','velocity','length','surface_tension',weber),
    }
    for name,spec in specs.items():
        keys,fn=spec[:-1],spec[-1]
        if all(k in kwargs for k in keys):out[name]=fn(*(kwargs[k] for k in keys))
    return out
