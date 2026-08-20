from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import math, json
import numpy as np
try:
    import cadquery as cq
    from cadquery import exporters, importers
    CADQUERY_AVAILABLE=True
except Exception:
    cq=None; CADQUERY_AVAILABLE=False
try:
    from OCP.IGESControl import IGESControl_Writer, IGESControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL
    from OCP.TopoDS import TopoDS
    OCP_IGES_AVAILABLE=True
except Exception:
    OCP_IGES_AVAILABLE=False

@dataclass(frozen=True)
class Point3:
    x:float; y:float; z:float
    def array(self): return np.array([self.x,self.y,self.z],float)
@dataclass(frozen=True)
class Vector3(Point3):
    def norm(self): return float(np.linalg.norm(self.array()))
    def unit(self):
        n=self.norm();
        if n==0: raise ValueError('zero vector')
        a=self.array()/n; return Vector3(*a)
@dataclass
class Frame:
    origin:Point3=Point3(0,0,0); R:np.ndarray=field(default_factory=lambda:np.eye(3))
    def matrix(self):
        T=np.eye(4); T[:3,:3]=np.asarray(self.R,float); T[:3,3]=self.origin.array(); return T
    def transform(self,p:Point3):
        q=self.R@p.array()+self.origin.array(); return Point3(*q)

def bspline_basis(i,p,u,knots):
    k=np.asarray(knots,float)
    if p==0:
        return 1.0 if (k[i] <= u < k[i+1] or (u==k[-1] and i+1==len(k)-1)) else 0.0
    a=0.0 if k[i+p]==k[i] else (u-k[i])/(k[i+p]-k[i])*bspline_basis(i,p-1,u,k)
    b=0.0 if k[i+p+1]==k[i+1] else (k[i+p+1]-u)/(k[i+p+1]-k[i+1])*bspline_basis(i+1,p-1,u,k)
    return a+b

@dataclass
class BSplineCurve:
    control:np.ndarray; degree:int; knots:np.ndarray
    def __post_init__(self):
        self.control=np.asarray(self.control,float); self.knots=np.asarray(self.knots,float)
        if len(self.knots)!=len(self.control)+self.degree+1: raise ValueError('invalid knot vector length')
    def evaluate(self,u):
        N=np.array([bspline_basis(i,self.degree,float(u),self.knots) for i in range(len(self.control))]); return N@self.control
    def derivative(self,u,h=1e-6): return (self.evaluate(u+h)-self.evaluate(u-h))/(2*h)
    def curvature(self,u,h=1e-5):
        d1=(self.evaluate(u+h)-self.evaluate(u-h))/(2*h); d2=(self.evaluate(u+h)-2*self.evaluate(u)+self.evaluate(u-h))/h**2
        n=np.linalg.norm(d1); den=max(n**3,1e-300)
        if self.control.shape[1]==3: return float(np.linalg.norm(np.cross(d1,d2))/den)
        if self.control.shape[1]==2:
            # Explicit planar scalar cross product.  NumPy deprecated
            # np.cross on 2-component vectors; this is mathematically
            # identical to |x' y'' - y' x''| and warning-free.
            cross2=d1[0]*d2[1]-d1[1]*d2[0]; return float(abs(cross2)/den)
        raise ValueError('curvature requires 2-D or 3-D control points')

@dataclass
class NURBSCurve(BSplineCurve):
    weights:np.ndarray=None
    def __post_init__(self):
        super().__post_init__(); self.weights=np.ones(len(self.control)) if self.weights is None else np.asarray(self.weights,float)
        if len(self.weights)!=len(self.control): raise ValueError('weights mismatch')
    def evaluate(self,u):
        N=np.array([bspline_basis(i,self.degree,float(u),self.knots) for i in range(len(self.control))]); W=N*self.weights; den=W.sum()
        if abs(den)<1e-300: raise ZeroDivisionError('NURBS weight denominator zero')
        return (W[:,None]*self.control).sum(axis=0)/den

@dataclass
class ShapeRecord:
    shape:object; semantic_id:str=''; metadata:dict=field(default_factory=dict)

class CadKernel:
    def __init__(self):
        if not CADQUERY_AVAILABLE: raise RuntimeError('CadQuery/OpenCascade backend unavailable')
    def box(self,x,y,z,semantic_id='box'): return ShapeRecord(cq.Workplane('XY').box(x,y,z),semantic_id)
    def cylinder(self,r,h,semantic_id='cylinder'): return ShapeRecord(cq.Workplane('XY').cylinder(h,r),semantic_id)
    def sphere(self,r,semantic_id='sphere'): return ShapeRecord(cq.Workplane('XY').sphere(r),semantic_id)
    def torus(self,r1,r2,semantic_id='torus'): return ShapeRecord(cq.Workplane('XY').transformed(rotate=(90,0,0)).moveTo(r1,0).circle(r2).revolve(360,(0,0),(0,1)),semantic_id)
    def union(self,a,b,semantic_id='union'): return ShapeRecord(a.shape.union(b.shape),semantic_id,{'parents':[a.semantic_id,b.semantic_id]})
    def difference(self,a,b,semantic_id='difference'): return ShapeRecord(a.shape.cut(b.shape),semantic_id,{'parents':[a.semantic_id,b.semantic_id]})
    def intersection(self,a,b,semantic_id='intersection'): return ShapeRecord(a.shape.intersect(b.shape),semantic_id,{'parents':[a.semantic_id,b.semantic_id]})
    def volume(self,a): return float(a.shape.val().Volume())
    def area(self,a): return float(a.shape.val().Area())
    def center_of_mass(self,a):
        c=a.shape.val().Center(); return np.array([c.x,c.y,c.z])
    def bounding_box(self,a):
        b=a.shape.val().BoundingBox(); return (b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax)
    def is_valid(self,a): return bool(a.shape.val().isValid())
    def export_step(self,a,path): exporters.export(a.shape,str(path),exportType=exporters.ExportTypes.STEP); return Path(path)
    def import_step(self,path,semantic_id='step_import'): return ShapeRecord(importers.importStep(str(path)),semantic_id)
    def export_iges(self,a,path):
        if not OCP_IGES_AVAILABLE: raise RuntimeError('OCP IGES unavailable')
        w=IGESControl_Writer(); w.AddShape(a.shape.val().wrapped); ok=w.Write(str(path));
        if not ok: raise RuntimeError('IGES write failed')
        return Path(path)
    def import_iges(self,path,semantic_id='iges_import'):
        if not OCP_IGES_AVAILABLE: raise RuntimeError('OCP IGES unavailable')
        r=IGESControl_Reader(); stat=r.ReadFile(str(path));
        if int(stat)!=int(IFSelect_RetDone): raise RuntimeError(f'IGES read status {stat}')
        r.TransferRoots(); sh=r.OneShape()
        # IGES frequently transfers closed solids as compounds of faces. Sew and rebuild a solid.
        sew=BRepBuilderAPI_Sewing(1e-6,True,True,True,False); ex=TopExp_Explorer(sh,TopAbs_FACE)
        while ex.More(): sew.Add(ex.Current()); ex.Next()
        sew.Perform(); sewn=sew.SewedShape(); shells=[]; ex=TopExp_Explorer(sewn,TopAbs_SHELL)
        while ex.More(): shells.append(TopoDS.Shell_s(ex.Current())); ex.Next()
        if len(shells)==1:
            maker=BRepBuilderAPI_MakeSolid(shells[0])
            if maker.IsDone(): return ShapeRecord(cq.Workplane(obj=cq.Shape.cast(maker.Solid())),semantic_id,{'healed_on_import':True})
        return ShapeRecord(cq.Workplane(obj=cq.Shape.cast(sewn)),semantic_id,{'healed_on_import':True,'solid_rebuild':False})
    def heal(self,a,tolerance=1e-7):
        # OpenCascade validation + clean operation; returns explicit audit rather than silent changes.
        before={'valid':self.is_valid(a),'volume':self.volume(a),'area':self.area(a)}
        cleaned=ShapeRecord(a.shape.clean(),a.semantic_id,{**a.metadata,'healed':True,'tolerance':tolerance})
        after={'valid':self.is_valid(cleaned),'volume':self.volume(cleaned),'area':self.area(cleaned)}
        audit={'operation':'clean/heal','tolerance':tolerance,'before':before,'after':after,'geometry_delta':abs(after['volume']-before['volume'])}
        return cleaned,audit

@dataclass
class Feature:
    name:str; operation:str; params:dict; parents:list[str]=field(default_factory=list); semantic_id:str=''; state:str='UNBUILT'; diagnostics:list[str]=field(default_factory=list)

class ParametricModel:
    def __init__(self,kernel=None): self.kernel=kernel or CadKernel(); self.features={}; self.shapes={}
    def add(self,feature:Feature):
        if feature.name in self.features: raise KeyError(feature.name)
        self.features[feature.name]=feature; return feature
    def _order(self):
        out=[]; temp=set(); done=set()
        def visit(n):
            if n in done:return
            if n in temp: raise ValueError('feature cycle')
            temp.add(n)
            for p in self.features[n].parents: visit(p)
            temp.remove(n); done.add(n); out.append(n)
        for n in self.features: visit(n)
        return out
    def rebuild(self):
        for n in self._order():
            f=self.features[n]
            try:
                if f.operation=='box': s=self.kernel.box(**f.params,semantic_id=f.semantic_id or n)
                elif f.operation=='cylinder': s=self.kernel.cylinder(**f.params,semantic_id=f.semantic_id or n)
                elif f.operation in ('union','difference','intersection'):
                    a,b=(self.shapes[p] for p in f.parents); s=getattr(self.kernel,f.operation)(a,b,f.semantic_id or n)
                else: raise NotImplementedError(f.operation)
                self.shapes[n]=s; f.state='BUILT'
            except Exception as e: f.state='FAILED'; f.diagnostics.append(repr(e)); raise
        return self.shapes

@dataclass
class AssemblyNode:
    name:str; shape:ShapeRecord|None=None; transform:np.ndarray=field(default_factory=lambda:np.eye(4)); children:list['AssemblyNode']=field(default_factory=list)
    def add(self,node): self.children.append(node); return node
    def validate(self):
        seen=set(); stack=set()
        def walk(x):
            i=id(x)
            if i in stack: raise ValueError('assembly cycle')
            if i in seen:return
            seen.add(i); stack.add(i)
            for c in x.children: walk(c)
            stack.remove(i)
        walk(self); return True


# ================= CELESTIAL DEPTH: CAD geometry/tolerance invariants =================
_BSpline_post_pre=BSplineCurve.__post_init__
def _celestial_bspline_post(self):
    _BSpline_post_pre(self)
    if self.control.ndim!=2 or len(self.control)<self.degree+1 or self.degree<1: raise ValueError('invalid B-spline degree/control net')
    if not np.all(np.isfinite(self.control)) or not np.all(np.isfinite(self.knots)): raise ValueError('B-spline data contain NaN/Inf')
    if np.any(np.diff(self.knots)<0): raise ValueError('knot vector must be nondecreasing')
BSplineCurve.__post_init__=_celestial_bspline_post

_NURBS_post_pre=NURBSCurve.__post_init__
def _celestial_nurbs_post(self):
    _NURBS_post_pre(self)
    if not np.all(np.isfinite(self.weights)): raise ValueError('NURBS weights contain NaN/Inf')
    if np.all(np.abs(self.weights)<=np.finfo(float).tiny): raise ValueError('all NURBS weights are zero')
NURBSCurve.__post_init__=_celestial_nurbs_post

_Frame_matrix_pre=Frame.matrix
def _celestial_frame_matrix(self):
    R=np.asarray(self.R,float)
    if R.shape!=(3,3) or not np.all(np.isfinite(R)): raise ValueError('frame rotation must be finite 3x3')
    defect=float(np.linalg.norm(R.T@R-np.eye(3)))
    if defect>1e-8: raise ValueError(f'frame rotation is not orthonormal; defect={defect:g}')
    if np.linalg.det(R)<=0: raise ValueError('frame rotation must be right-handed')
    return _Frame_matrix_pre(self)
Frame.matrix=_celestial_frame_matrix

for _name in ('box','cylinder','sphere','torus'):
    _old=getattr(CadKernel,_name)
    def _make(old,name):
        def wrapped(self,*args,**kwargs):
            nums=[]
            for a in args:
                if isinstance(a,(int,float,np.number)): nums.append(float(a))
            for k,v in kwargs.items():
                if k!='semantic_id' and isinstance(v,(int,float,np.number)): nums.append(float(v))
            if nums and (not np.isfinite(nums).all() or min(nums)<=0): raise ValueError(f'{name} dimensions/radii must be positive finite')
            return old(self,*args,**kwargs)
        return wrapped
    setattr(CadKernel,_name,_make(_old,_name))

_heal_pre=CadKernel.heal
def _celestial_heal(self,a,tolerance=1e-7):
    tolerance=float(tolerance)
    if not np.isfinite(tolerance) or tolerance<=0: raise ValueError('heal tolerance must be positive finite')
    out,audit=_heal_pre(self,a,tolerance)
    scale=max(1.0,abs(audit['before']['volume']))
    audit['relative_volume_delta']=float(audit['geometry_delta']/scale)
    audit['status']='VALID' if audit['after']['valid'] else 'INVALID_AFTER_HEAL'
    return out,audit
CadKernel.heal=_celestial_heal

_Assembly_validate_pre=AssemblyNode.validate
def _celestial_assembly_validate(self):
    ok=_Assembly_validate_pre(self)
    seen=set()
    def walk(x):
        if id(x) in seen:return
        seen.add(id(x));T=np.asarray(x.transform,float)
        if T.shape!=(4,4) or not np.all(np.isfinite(T)) or not np.allclose(T[3],[0,0,0,1],atol=1e-12): raise ValueError(f'invalid homogeneous transform on assembly node {x.name}')
        for c in x.children:walk(c)
    walk(self);return ok
AssemblyNode.validate=_celestial_assembly_validate
