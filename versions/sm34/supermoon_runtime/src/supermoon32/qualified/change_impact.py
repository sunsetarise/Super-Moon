from __future__ import annotations
from dataclasses import dataclass,field
from collections import defaultdict,deque
from ..core import InvalidInput

@dataclass
class ChangeImpactAnalyzer:
    dependencies:dict[str,set[str]]=field(default_factory=lambda:defaultdict(set))
    tests_by_component:dict[str,set[str]]=field(default_factory=lambda:defaultdict(set))
    qualification_by_component:dict[str,set[str]]=field(default_factory=lambda:defaultdict(set))
    def add_dependency(self,component,dependent):self.dependencies[str(component)].add(str(dependent))
    def add_test(self,component,test):self.tests_by_component[str(component)].add(str(test))
    def add_qualification(self,component,claim):self.qualification_by_component[str(component)].add(str(claim))
    def affected(self,changed):
        q=deque(map(str,changed));seen=set(q)
        while q:
            x=q.popleft()
            for y in self.dependencies.get(x,()):
                if y not in seen:seen.add(y);q.append(y)
        return seen
    def plan(self,changed,critical=False):
        comps=self.affected(changed);tests=sorted({t for c in comps for t in self.tests_by_component.get(c,())});claims=sorted({q for c in comps for q in self.qualification_by_component.get(c,())})
        return {'affected_components':sorted(comps),'tests':tests,'qualification_claims':claims,'full_qualification_required':bool(critical)}
