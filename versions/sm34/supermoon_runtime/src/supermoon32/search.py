from __future__ import annotations
import heapq, math, random
from dataclasses import dataclass
from .core import *
def astar(start,goal_test,neighbors,heuristic=lambda s:0.):
    pq=[(float(heuristic(start)),0,start)];g={start:0.};prev={};counter=0
    while pq:
        _,_,u=heapq.heappop(pq)
        if goal_test(u):
            path=[u]
            while path[-1]!=start:path.append(prev[path[-1]])
            return SolverResult(list(reversed(path)),True,len(g),0.,'goal',diagnostics={'cost':g[u]})
        for v,c in neighbors(u):
            c=float(c)
            if c<0:raise InvalidInput('negative edge cost')
            ng=g[u]+c
            if ng<g.get(v,math.inf):g[v]=ng;prev[v]=u;counter+=1;heapq.heappush(pq,(ng+float(heuristic(v)),counter,v))
    return SolverResult(None,False,len(g),math.inf,'no_path',status='NOT_FOUND')
@dataclass
class MCTSNode:
    state: object; parent: object=None; action: object=None; visits:int=0; value:float=0.; children:list=None; untried:list=None
    def __post_init__(self):
        if self.children is None:self.children=[]

def mcts(root_state,actions,transition,reward,is_terminal,iterations=1000,exploration=math.sqrt(2),seed=0,rollout_depth=100):
    rng=random.Random(seed);root=MCTSNode(root_state);root.untried=list(actions(root_state))
    for _ in range(int(iterations)):
        node=root;state=root_state
        while not node.untried and node.children and not is_terminal(state):
            node=max(node.children,key=lambda c:c.value/max(c.visits,1)+exploration*math.sqrt(math.log(max(node.visits,1))/max(c.visits,1)));state=transition(state,node.action)
        if not is_terminal(state) and node.untried:
            a=node.untried.pop(rng.randrange(len(node.untried)));state=transition(state,a);child=MCTSNode(state,node,a);child.untried=list(actions(state));node.children.append(child);node=child
        total=0.;depth=0;s=state
        while not is_terminal(s) and depth<rollout_depth:
            aa=list(actions(s))
            if not aa:break
            a=rng.choice(aa);s=transition(s,a);depth+=1
        total=float(reward(s))
        while node is not None:node.visits+=1;node.value+=total;node=node.parent
    if not root.children:return None,root
    best=max(root.children,key=lambda c:c.visits);return best.action,root
