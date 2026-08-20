from __future__ import annotations
from dataclasses import dataclass
import numpy as np
@dataclass
class Mesh:
    nodes:np.ndarray; cells:dict; boundaries:dict=None
    def __post_init__(self): self.nodes=np.asarray(self.nodes,float); self.cells={k:np.asarray(v,int) for k,v in self.cells.items()}; self.boundaries=self.boundaries or {}

def line_mesh(length,n):
    x=np.linspace(0,length,n+1)[:,None]; return Mesh(np.c_[x,np.zeros((n+1,2))],{'line2':np.c_[np.arange(n),np.arange(1,n+1)]})
def quad_mesh(Lx,Ly,nx,ny):
    nodes=np.array([[i*Lx/nx,j*Ly/ny,0.] for j in range(ny+1) for i in range(nx+1)])
    q=[]
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i; q.append([a,a+1,a+nx+2,a+nx+1])
    return Mesh(nodes,{'quad4':np.asarray(q,int)})
def tri_mesh(Lx,Ly,nx,ny):
    q=quad_mesh(Lx,Ly,nx,ny); tris=[]
    for a,b,c,d in q.cells['quad4']: tris += [[a,b,c],[a,c,d]]
    return Mesh(q.nodes,{'tri3':np.asarray(tris,int)})
def tet_box(Lx,Ly,Lz,nx,ny,nz):
    # structured cubes split into six positive-orientation tetrahedra
    nodes=np.array([[i*Lx/nx,j*Ly/ny,k*Lz/nz] for k in range(nz+1) for j in range(ny+1) for i in range(nx+1)],float)
    def I(i,j,k): return k*(ny+1)*(nx+1)+j*(nx+1)+i
    t=[]
    pattern=[(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6),(0,5,1,6)]
    for k in range(nz):
      for j in range(ny):
       for i in range(nx):
        v=[I(i,j,k),I(i+1,j,k),I(i+1,j+1,k),I(i,j+1,k),I(i,j,k+1),I(i+1,j,k+1),I(i+1,j+1,k+1),I(i,j+1,k+1)]
        for p in pattern:
            ids=[v[z] for z in p]; X=nodes[ids]; det=np.linalg.det(np.c_[X[1:]-X[0]])
            if det<0: ids[2],ids[3]=ids[3],ids[2]
            t.append(ids)
    return Mesh(nodes,{'tet4':np.asarray(t,int)})
def triangle_quality(X):
    X=np.asarray(X,float); l=[np.linalg.norm(X[(i+1)%3]-X[i]) for i in range(3)]; A=0.5*np.linalg.norm(np.cross(X[1]-X[0],X[2]-X[0])); return float(4*np.sqrt(3)*A/max(sum(v*v for v in l),1e-300))
def tet_quality(X):
    X=np.asarray(X,float); V=abs(np.linalg.det(np.vstack((X[1]-X[0],X[2]-X[0],X[3]-X[0]))))/6; edges=[np.linalg.norm(X[j]-X[i]) for i in range(4) for j in range(i+1,4)]; return float(12*(3*V)**(2/3)/max(sum(e*e for e in edges),1e-300))
def boundary_layer(first,growth,n): return first*growth**np.arange(n)
def boundary_layer_total(first,growth,n): return float(first*n if abs(growth-1)<1e-14 else first*(growth**n-1)/(growth-1))
def first_layer_from_total(total,growth,n): return float(total/n if abs(growth-1)<1e-14 else total*(growth-1)/(growth**n-1))


# ================= CELESTIAL DEPTH: mesh validity / degeneracy contracts =================
_Mesh_post_pre_celestial=Mesh.__post_init__
def _celestial_mesh_post(self):
    _Mesh_post_pre_celestial(self)
    if self.nodes.ndim!=2 or self.nodes.shape[0]==0 or self.nodes.shape[1] not in (2,3): raise ValueError('mesh nodes must be non-empty N x 2/3')
    if not np.all(np.isfinite(self.nodes)): raise ValueError('mesh nodes contain NaN/Inf')
    n=len(self.nodes)
    for name,c in self.cells.items():
        if c.ndim!=2: raise ValueError(f'cell block {name} must be 2-D')
        if c.size and (np.min(c)<0 or np.max(c)>=n): raise IndexError(f'cell block {name} references out-of-range node')
Mesh.__post_init__=_celestial_mesh_post

def _mesh_counts(*vals):
    out=[]
    for v in vals:
        if int(v)!=v or int(v)<=0: raise ValueError('mesh counts must be positive integers')
        out.append(int(v))
    return out

def line_mesh(length,n):
    length=float(length);n=_mesh_counts(n)[0]
    if not np.isfinite(length) or length<=0: raise ValueError('length must be positive finite')
    x=np.linspace(0,length,n+1)[:,None]; return Mesh(np.c_[x,np.zeros((n+1,2))],{'line2':np.c_[np.arange(n),np.arange(1,n+1)]})
def quad_mesh(Lx,Ly,nx,ny):
    Lx=float(Lx);Ly=float(Ly);nx,ny=_mesh_counts(nx,ny)
    if not np.isfinite([Lx,Ly]).all() or min(Lx,Ly)<=0: raise ValueError('positive finite dimensions required')
    nodes=np.array([[i*Lx/nx,j*Ly/ny,0.] for j in range(ny+1) for i in range(nx+1)])
    q=[]
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i;q.append([a,a+1,a+nx+2,a+nx+1])
    return Mesh(nodes,{'quad4':np.asarray(q,int)})
def tri_mesh(Lx,Ly,nx,ny):
    q=quad_mesh(Lx,Ly,nx,ny);tris=[]
    for a,b,c,d in q.cells['quad4']:tris += [[a,b,c],[a,c,d]]
    return Mesh(q.nodes,{'tri3':np.asarray(tris,int)})
_tet_box_pre_celestial=tet_box
def tet_box(Lx,Ly,Lz,nx,ny,nz):
    vals=np.asarray([Lx,Ly,Lz],float);nx,ny,nz=_mesh_counts(nx,ny,nz)
    if np.any(~np.isfinite(vals)) or np.any(vals<=0): raise ValueError('positive finite box dimensions required')
    m=_tet_box_pre_celestial(*vals,nx,ny,nz)
    for tet in m.cells['tet4']:
        X=m.nodes[tet];det=float(np.linalg.det(np.c_[X[1:]-X[0]]))
        if not np.isfinite(det) or det<=np.finfo(float).eps*max(1.0,float(np.linalg.norm(X))**3): raise ValueError('degenerate/inverted tetrahedron generated')
    return m

def triangle_quality(X):
    X=np.asarray(X,float)
    if X.shape not in ((3,2),(3,3)) or not np.all(np.isfinite(X)): raise ValueError('triangle coordinates must be finite 3x2/3')
    if X.shape[1]==2:X=np.c_[X,np.zeros(3)]
    l=[np.linalg.norm(X[(i+1)%3]-X[i]) for i in range(3)];A=.5*np.linalg.norm(np.cross(X[1]-X[0],X[2]-X[0]));den=sum(v*v for v in l)
    return 0.0 if den<=np.finfo(float).tiny else float(4*np.sqrt(3)*A/den)
def tet_quality(X):
    X=np.asarray(X,float)
    if X.shape!=(4,3) or not np.all(np.isfinite(X)): raise ValueError('tetrahedron coordinates must be finite 4x3')
    V=abs(np.linalg.det(np.vstack((X[1]-X[0],X[2]-X[0],X[3]-X[0]))))/6;edges=[np.linalg.norm(X[j]-X[i]) for i in range(4) for j in range(i+1,4)];den=sum(e*e for e in edges)
    return 0.0 if den<=np.finfo(float).tiny else float(12*(3*V)**(2/3)/den)
def boundary_layer(first,growth,n):
    first=float(first);growth=float(growth);n=_mesh_counts(n)[0]
    if not np.isfinite([first,growth]).all() or first<=0 or growth<=0: raise ValueError('positive finite first/growth required')
    return first*growth**np.arange(n)
def boundary_layer_total(first,growth,n):
    a=boundary_layer(first,growth,n);return float(np.sum(a))
def first_layer_from_total(total,growth,n):
    total=float(total);growth=float(growth);n=_mesh_counts(n)[0]
    if not np.isfinite([total,growth]).all() or total<=0 or growth<=0: raise ValueError('positive finite total/growth required')
    den=float(n if abs(growth-1)<1e-14 else (growth**n-1)/(growth-1))
    if not np.isfinite(den) or den<=0: raise FloatingPointError('NUMERICAL_BREAKDOWN: invalid layer-series denominator')
    return float(total/den)
