from __future__ import annotations
from dataclasses import dataclass
import numpy as np, math
from .core import *
try:
    from supermoon31.fea import truss2d, cst_stiffness, solve_tet4, elasticity_matrix, newmark, modal, buckling, thermal_bar, j2_radial_return, laminate_abd
except Exception:
    truss2d=cst_stiffness=solve_tet4=elasticity_matrix=newmark=modal=buckling=thermal_bar=j2_radial_return=laminate_abd=None
@dataclass
class BarResult:
    displacement: np.ndarray; reactions: np.ndarray; stress: np.ndarray; strain: np.ndarray; residual_norm: float

def bar1d(nodes,elements,E,A,loads=None,fixed=None):
    x=finite_array(nodes,'nodes',1);elements=np.asarray(elements,int);n=len(x);E=float(E);A=float(A)
    if E<=0 or A<=0 or elements.ndim!=2 or elements.shape[1]!=2:raise InvalidInput('invalid bar model')
    K=np.zeros((n,n));stress_ops=[]
    for e,(i,j) in enumerate(elements):
        if i<0 or j<0 or i>=n or j>=n or i==j:raise InvalidInput('invalid element')
        L=abs(x[j]-x[i])
        if L<=DEFAULT_TOLERANCE.geometry:raise DegenerateGeometry('zero-length bar')
        ke=E*A/L*np.array([[1,-1],[-1,1]],float);dof=[i,j];K[np.ix_(dof,dof)]+=ke;stress_ops.append((i,j,L))
    f=np.zeros(n)
    if loads:
        for i,v in loads.items():f[int(i)]+=float(v)
    fixed=sorted(set(int(i) for i in (fixed or [])));free=np.array([i for i in range(n) if i not in fixed],int)
    if len(free)==0:u=np.zeros(n)
    else:
        Kff=K[np.ix_(free,free)]
        if np.linalg.matrix_rank(Kff)<len(free):raise SingularSystem('underconstrained bar system')
        u=np.zeros(n);u[free]=np.linalg.solve(Kff,f[free])
    reactions=K@u-f;strain=np.array([(u[j]-u[i])/L for i,j,L in stress_ops]);stress=E*strain;res=float(np.linalg.norm((K@u-f)[free])) if len(free) else 0.0;return BarResult(u,reactions,stress,strain,res)

def triangle3_plane_stress_stiffness(coords,E,nu,thickness=1.0):
    P=finite_array(coords,'coords',2)
    if P.shape!=(3,2):raise DimensionMismatch('triangle coords must be 3x2')
    x1,y1=P[0];x2,y2=P[1];x3,y3=P[2];A=.5*((x2-x1)*(y3-y1)-(x3-x1)*(y2-y1))
    if abs(A)<=DEFAULT_TOLERANCE.geometry:raise DegenerateGeometry('degenerate triangle')
    b=np.array([y2-y3,y3-y1,y1-y2]);c=np.array([x3-x2,x1-x3,x2-x1]);B=np.zeros((3,6))
    for i in range(3):B[0,2*i]=b[i];B[1,2*i+1]=c[i];B[2,2*i]=c[i];B[2,2*i+1]=b[i]
    B/=2*A;D=E/(1-nu**2)*np.array([[1,nu,0],[nu,1,0],[0,0,(1-nu)/2]]);K=thickness*abs(A)*(B.T@D@B);return K,B,D,abs(A)
def assemble(elements,n_dof):
    K=np.zeros((n_dof,n_dof))
    for dofs,ke in elements:
        d=np.asarray(dofs,int);ke=np.asarray(ke,float)
        if ke.shape!=(len(d),len(d)):raise DimensionMismatch('element stiffness mismatch')
        K[np.ix_(d,d)]+=ke
    return K
def solve_linear(K,f,fixed=(),prescribed=None):
    K=finite_array(K,'K',2);f=finite_array(f,'f',1);n=len(f)
    if K.shape!=(n,n):raise DimensionMismatch('K/f mismatch')
    u=np.zeros(n);prescribed=prescribed or {}
    fixed_set=set(map(int,fixed))|set(map(int,prescribed.keys()))
    for i,v in prescribed.items():u[int(i)]=float(v)
    free=np.array([i for i in range(n) if i not in fixed_set],int);known=np.array(sorted(fixed_set),int)
    rhs=f[free]-K[np.ix_(free,known)]@u[known] if len(known) else f[free]
    if len(free):
        Kff=K[np.ix_(free,free)]
        if np.linalg.matrix_rank(Kff)<len(free):raise SingularSystem('singular constrained system')
        u[free]=np.linalg.solve(Kff,rhs)
    r=K@u-f;return SolverResult(u,True,1,float(np.linalg.norm(r[free])) if len(free) else 0.,'direct',diagnostics={'reactions':r})
