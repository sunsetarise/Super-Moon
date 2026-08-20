from __future__ import annotations
import heapq, collections, math
from .core import *
def _adj(graph,u):return graph.get(u,{}) if isinstance(graph,dict) else {}
def bfs(graph,start):
    q=collections.deque([start]);seen={start};order=[]
    while q:
        u=q.popleft();order.append(u)
        neigh=_adj(graph,u);it=neigh.keys() if isinstance(neigh,dict) else neigh
        for v in it:
            if v not in seen:seen.add(v);q.append(v)
    return order
def dfs(graph,start):
    st=[start];seen=set();order=[]
    while st:
        u=st.pop()
        if u in seen:continue
        seen.add(u);order.append(u);neigh=_adj(graph,u);it=list(neigh.keys() if isinstance(neigh,dict) else neigh);st.extend(reversed(it))
    return order
def dijkstra(graph,start,goal=None):
    dist={start:0.};prev={};pq=[(0.,start)]
    while pq:
        d,u=heapq.heappop(pq)
        if d!=dist[u]:continue
        if u==goal:break
        neigh=_adj(graph,u)
        items=neigh.items() if isinstance(neigh,dict) else ((v,1.) for v in neigh)
        for v,w in items:
            w=float(w)
            if w<0:raise InvalidInput('negative weights not supported')
            nd=d+w
            if nd<dist.get(v,math.inf):dist[v]=nd;prev[v]=u;heapq.heappush(pq,(nd,v))
    return dist,prev
def path_from_prev(prev,start,goal):
    if goal!=start and goal not in prev:return None
    p=[goal]
    while p[-1]!=start:p.append(prev[p[-1]])
    return list(reversed(p))
def connected_components(graph):
    nodes=set(graph)
    for u in graph:
        neigh=_adj(graph,u);nodes.update(neigh.keys() if isinstance(neigh,dict) else neigh)
    comps=[]
    while nodes:
        s=next(iter(nodes));c=set(bfs(graph,s));comps.append(c);nodes-=c
    return comps
