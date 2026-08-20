from __future__ import annotations
from dataclasses import dataclass,field
import numpy as np
from .core import *
try:
    from supermoon31.cad import BSplineCurve,NURBSCurve,Frame,Point3,Vector3
except Exception:
    BSplineCurve=NURBSCurve=Frame=Point3=Vector3=None
@dataclass(frozen=True)
class Vertex: id:int; point:tuple[float,float,float]
@dataclass(frozen=True)
class Edge: id:int; v0:int; v1:int
@dataclass
class Wire: id:int; edges:list[int]
@dataclass
class Face: id:int; outer_wire:int; inner_wires:list[int]=field(default_factory=list)
@dataclass
class Shell: id:int; faces:list[int]=field(default_factory=list)
@dataclass
class Solid: id:int; shells:list[int]=field(default_factory=list)
@dataclass
class BRepModel:
    vertices:dict[int,Vertex]=field(default_factory=dict);edges:dict[int,Edge]=field(default_factory=dict);wires:dict[int,Wire]=field(default_factory=dict);faces:dict[int,Face]=field(default_factory=dict);shells:dict[int,Shell]=field(default_factory=dict);solids:dict[int,Solid]=field(default_factory=dict)
    def validate(self):
        errors=[]
        for e in self.edges.values():
            if e.v0 not in self.vertices or e.v1 not in self.vertices:errors.append(f'edge {e.id} missing vertex')
            elif e.v0==e.v1:errors.append(f'edge {e.id} degenerate')
        for w in self.wires.values():
            if not w.edges:errors.append(f'wire {w.id} empty')
            if any(e not in self.edges for e in w.edges):errors.append(f'wire {w.id} missing edge')
        for f in self.faces.values():
            if f.outer_wire not in self.wires or any(w not in self.wires for w in f.inner_wires):errors.append(f'face {f.id} invalid wire')
        for s in self.shells.values():
            if any(f not in self.faces for f in s.faces):errors.append(f'shell {s.id} missing face')
        for s in self.solids.values():
            if any(sh not in self.shells for sh in s.shells):errors.append(f'solid {s.id} missing shell')
        return {'valid':not errors,'errors':errors,'counts':{k:len(getattr(self,k)) for k in ['vertices','edges','wires','faces','shells','solids']}}
    def add_vertex(self,p):
        p=tuple(map(float,p));
        if len(p)!=3 or not np.all(np.isfinite(p)):raise InvalidInput('finite 3D point required')
        i=max(self.vertices.keys(),default=-1)+1;self.vertices[i]=Vertex(i,p);return i
    def add_edge(self,v0,v1):
        i=max(self.edges.keys(),default=-1)+1;self.edges[i]=Edge(i,int(v0),int(v1));return i
