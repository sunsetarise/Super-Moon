from __future__ import annotations
from dataclasses import dataclass
import numpy as np, math
from .core import *
@dataclass(frozen=True)
class Point:
    xyz: tuple[float,...]
    def array(self):return np.asarray(self.xyz,float)

def distance(a,b):return stable_norm(np.asarray(a,float)-np.asarray(b,float))
def orientation2d(a,b,c,tol=DEFAULT_TOLERANCE):
    a,b,c=map(lambda z:finite_array(z,'point',1),[a,b,c])
    if not(len(a)==len(b)==len(c)==2):raise DimensionMismatch('2D points required')
    cross=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);scale=max(1.,distance(a,b)*distance(a,c));eps=tol.geometry*scale
    return 1 if cross>eps else -1 if cross<-eps else 0
def segment_intersection(a,b,c,d,tol=DEFAULT_TOLERANCE):
    a,b,c,d=[np.asarray(x,float) for x in (a,b,c,d)];r=b-a;s=d-c;den=r[0]*s[1]-r[1]*s[0];q=c-a;numt=q[0]*s[1]-q[1]*s[0];numu=q[0]*r[1]-q[1]*r[0];eps=tol.geometry*max(1.,np.linalg.norm(r)*np.linalg.norm(s))
    if abs(den)<=eps:return None
    t=numt/den;u=numu/den
    if -tol.geometry<=t<=1+tol.geometry and -tol.geometry<=u<=1+tol.geometry:return a+t*r
    return None
def project_point_segment(p,a,b):
    p,a,b=[np.asarray(x,float) for x in (p,a,b)];d=b-a;den=float(d@d)
    if den<=DEFAULT_TOLERANCE.geometry**2:raise DegenerateGeometry('zero-length segment')
    t=float((p-a)@d/den);tc=min(1.,max(0.,t));q=a+tc*d;return q,tc,distance(p,q)
def plane_projection(p,origin,normal):
    p=np.asarray(p,float);o=np.asarray(origin,float);n=safe_normalize(normal);return p-n*float((p-o)@n)
def aabb(points):
    P=finite_array(points,'points',2);return P.min(axis=0),P.max(axis=0)
def rotation_matrix_2d(theta):
    c=math.cos(theta);s=math.sin(theta);return np.array([[c,-s],[s,c]])
def triangle_area(a,b,c):
    a,b,c=[np.asarray(x,float) for x in (a,b,c)];
    if len(a)==2:return abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
    return np.linalg.norm(np.cross(b-a,c-a))/2
