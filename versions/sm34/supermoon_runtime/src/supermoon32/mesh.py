from __future__ import annotations
from dataclasses import dataclass
import numpy as np, math
from .core import *
from .geometry import triangle_area
@dataclass
class TriMesh:
    nodes: np.ndarray; elements: np.ndarray
    def __post_init__(self):
        self.nodes=finite_array(self.nodes,'nodes',2);self.elements=np.asarray(self.elements,int)
        if self.elements.ndim!=2 or self.elements.shape[1]!=3:raise DimensionMismatch('triangles require Mx3 connectivity')
        if np.any(self.elements<0) or np.any(self.elements>=len(self.nodes)):raise InvalidInput('element index out of bounds')
        if len({tuple(sorted(e)) for e in self.elements})!=len(self.elements):raise InvalidInput('duplicate elements')
    def adjacency(self):
        adj=[set() for _ in range(len(self.nodes))]
        for e in self.elements:
            for i in e:
                for j in e:
                    if i!=j:adj[i].add(int(j))
        return [sorted(x) for x in adj]
    def boundary_edges(self):
        counts={}
        for e in self.elements:
            for a,b in ((e[0],e[1]),(e[1],e[2]),(e[2],e[0])):
                key=tuple(sorted((int(a),int(b))));counts[key]=counts.get(key,0)+1
        return np.array([k for k,v in counts.items() if v==1],int)
    def areas(self):return np.array([triangle_area(*self.nodes[e]) for e in self.elements])
    def quality(self):
        q=[]
        for e in self.elements:
            P=self.nodes[e];l=[np.linalg.norm(P[(i+1)%3]-P[i]) for i in range(3)];A=triangle_area(*P);q.append(4*math.sqrt(3)*A/max(sum(x*x for x in l),np.finfo(float).tiny))
        return np.array(q)
    def validate(self):
        a=self.areas();q=self.quality();return {'nodes':len(self.nodes),'elements':len(self.elements),'min_area':float(a.min()),'min_quality':float(q.min()),'valid':bool(np.all(a>DEFAULT_TOLERANCE.geometry) and np.all(q>0))}
def rectangular_tri_mesh(nx,ny,lx=1.,ly=1.):
    nx=int(nx);ny=int(ny)
    if nx<1 or ny<1:raise InvalidInput('nx,ny >= 1')
    xs=np.linspace(0,lx,nx+1);ys=np.linspace(0,ly,ny+1);nodes=np.array([(x,y) for y in ys for x in xs]);els=[]
    idx=lambda i,j:j*(nx+1)+i
    for j in range(ny):
        for i in range(nx):a=idx(i,j);b=idx(i+1,j);c=idx(i+1,j+1);d=idx(i,j+1);els += [(a,b,c),(a,c,d)]
    return TriMesh(nodes,np.array(els,int))
