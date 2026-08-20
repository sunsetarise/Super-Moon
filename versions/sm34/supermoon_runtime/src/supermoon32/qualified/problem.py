from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
from collections import defaultdict, deque
from ..core import InvalidInput, DimensionMismatch

@dataclass(frozen=True)
class Dimension:
    # SI base exponents: kg, m, s, A, K, mol, cd
    exponents: tuple[float,float,float,float,float,float,float]=(0,0,0,0,0,0,0)
    def __mul__(self,o:'Dimension')->'Dimension':return Dimension(tuple(a+b for a,b in zip(self.exponents,o.exponents)))
    def __truediv__(self,o:'Dimension')->'Dimension':return Dimension(tuple(a-b for a,b in zip(self.exponents,o.exponents)))
    def __pow__(self,p:float)->'Dimension':return Dimension(tuple(a*p for a in self.exponents))
    def compatible(self,o:'Dimension',tol=1e-12)->bool:return all(abs(a-b)<=tol for a,b in zip(self.exponents,o.exponents))

DIMENSIONLESS=Dimension()
MASS=Dimension((1,0,0,0,0,0,0)); LENGTH=Dimension((0,1,0,0,0,0,0)); TIME=Dimension((0,0,1,0,0,0,0)); TEMPERATURE=Dimension((0,0,0,0,1,0,0))
VELOCITY=LENGTH/TIME; ACCELERATION=LENGTH/(TIME**2); FORCE=MASS*ACCELERATION; PRESSURE=FORCE/(LENGTH**2); ENERGY=FORCE*LENGTH

@dataclass(frozen=True)
class EquationDimensionalCheck:
    equation_id:str; lhs:Dimension; rhs:Dimension
    @property
    def passed(self):return self.lhs.compatible(self.rhs)
    def enforce(self):
        if not self.passed: raise DimensionMismatch(f'dimensional inconsistency in {self.equation_id}: {self.lhs.exponents} != {self.rhs.exponents}')
        return True

@dataclass
class ProblemDefinition:
    problem_id:str
    domain:str
    governing_equations:list[str]
    unknown_variables:list[str]
    initial_conditions:dict=field(default_factory=dict)
    boundary_conditions:dict=field(default_factory=dict)
    material_models:dict=field(default_factory=dict)
    constitutive_models:dict=field(default_factory=dict)
    constraints:list=field(default_factory=list)
    objectives:list=field(default_factory=list)
    uncertain_parameters:dict=field(default_factory=dict)
    observables:list[str]=field(default_factory=list)
    validation_targets:list=field(default_factory=list)
    acceptance_criteria:dict=field(default_factory=dict)
    units:dict=field(default_factory=dict)
    coordinate_system:str='Cartesian'
    reference_frame:str='inertial'
    assumptions:list[str]=field(default_factory=list)
    validity_domain:dict=field(default_factory=dict)
    def validate(self):
        if not self.problem_id.strip():raise InvalidInput('problem_id required')
        if not self.domain.strip():raise InvalidInput('domain required')
        if not self.governing_equations:raise InvalidInput('governing_equations required')
        if not self.unknown_variables:raise InvalidInput('unknown_variables required')
        return True

class EquationGraph:
    def __init__(self):self.nodes:set[str]=set();self.edges:dict[str,set[str]]=defaultdict(set)
    def add_node(self,node:str):
        if not node:raise InvalidInput('empty graph node')
        self.nodes.add(node);return node
    def add_dependency(self,source:str,target:str):
        self.add_node(source);self.add_node(target);self.edges[source].add(target)
    def topological_order(self)->list[str]:
        indeg={n:0 for n in self.nodes}
        for a,bs in self.edges.items():
            for b in bs:indeg[b]+=1
        q=deque(sorted(n for n,d in indeg.items() if d==0));out=[]
        while q:
            n=q.popleft();out.append(n)
            for b in sorted(self.edges.get(n,())):
                indeg[b]-=1
                if indeg[b]==0:q.append(b)
        if len(out)!=len(self.nodes):raise InvalidInput('equation dependency graph contains a cycle')
        return out
    def missing_dependencies(self,declared:Iterable[str])->set[str]:
        d=set(declared); referenced={x for k,vs in self.edges.items() for x in (k,*vs)};return referenced-d

@dataclass(frozen=True)
class Regime:
    domain:str; labels:tuple[str,...]; diagnostics:dict

def detect_cfd_regime(mach:float,reynolds:float,knudsen:float=0.0)->Regime:
    if min(mach,reynolds,knudsen)<0:raise InvalidInput('regime numbers must be non-negative')
    comp='incompressible' if mach<0.3 else 'transonic' if mach<1.2 else 'supersonic' if mach<5 else 'hypersonic'
    visc='laminar' if reynolds<5e5 else 'transitional' if reynolds<3e6 else 'turbulent'
    cont='continuum' if knudsen<1e-3 else 'slip_flow' if knudsen<0.1 else 'rarefied'
    return Regime('CFD',(comp,visc,cont),{'Mach':mach,'Reynolds':reynolds,'Knudsen':knudsen})

def detect_structural_regime(geometric_nonlinearity=False,material_nonlinearity=False,contact=False,dynamic=False)->Regime:
    labels=['dynamic' if dynamic else 'static','geometrically_nonlinear' if geometric_nonlinearity else 'small_deformation','materially_nonlinear' if material_nonlinearity else 'linear_material']
    if contact:labels.append('contact')
    return Regime('STRUCTURES',tuple(labels),{})
