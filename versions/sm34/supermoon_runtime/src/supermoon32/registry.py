from __future__ import annotations
from . import numerics,sparse,optimization,ode,pde,cfd,fea,geometry,mesh,uq,graph,search,ml
REGISTRY={
'root.bisection':numerics.bisection,'root.secant':numerics.secant,'root.newton':numerics.newton_scalar,'root.brent':numerics.brent,
'nonlinear.newton_system':numerics.newton_system,'sparse.cg':sparse.cg,'sparse.gmres':sparse.gmres,'sparse.bicgstab':sparse.bicgstab,
'opt.gradient_descent':optimization.gradient_descent,'opt.bfgs':optimization.bfgs,'opt.lbfgs':optimization.lbfgs,'opt.nelder_mead':optimization.nelder_mead,
'ode.euler':ode.euler,'ode.midpoint':ode.midpoint,'ode.rk4':ode.rk4,'ode.rk45':ode.rk45,'pde.heat1d':pde.heat_1d_explicit,'pde.poisson1d':pde.poisson_1d_dirichlet,
'cfd.euler2d':cfd.euler_2d_cartesian,'fea.bar1d':fea.bar1d,'geometry.orientation2d':geometry.orientation2d,'mesh.rect_tri':mesh.rectangular_tri_mesh,
'uq.monte_carlo':uq.monte_carlo,'graph.dijkstra':graph.dijkstra,'search.astar':search.astar,'ml.attention':ml.attention}
def registry_integrity():
    bad=[k for k,v in REGISTRY.items() if not callable(v)];return {'count':len(REGISTRY),'bad':bad,'passed':not bad}
def resolve(name):return REGISTRY[name]
