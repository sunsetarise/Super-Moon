import json, math, os, tempfile
import numpy as np
import pytest
from supermoon32 import *

def square(x): return x*x

def test_core_errors_and_timed():
    with pytest.raises(InvalidInput): finite_array([])
    with pytest.raises(DimensionMismatch): finite_array([[1]],ndim=1)
    with pytest.raises(InvalidInput): finite_array([np.nan])
    with pytest.raises(InvalidInput): finite_scalar('x')
    with pytest.raises(InvalidInput): finite_scalar(np.inf)
    with pytest.raises(NumericalOverflow): stable_polyval([1e308,1e308],1e308)
    out,dt=timed_call(lambda x:x+1,2); assert out==3 and dt>=0

def test_numerics_error_and_extra_paths():
    with pytest.raises(SingularSystem): numerics.lu_factor([[1,2],[2,4]])
    with pytest.raises(InvalidInput): numerics.cholesky([[1,2],[2,1]])
    assert numerics.bisection(lambda x:x,0,1).solution==0
    assert numerics.bisection(lambda x:x-1,0,1).solution==1
    with pytest.raises(ConvergenceFailure): numerics.secant(lambda x:1.,0,1)
    with pytest.raises(ConvergenceFailure): numerics.newton_scalar(lambda x:x*x+1,lambda x:0.,0)
    r=numerics.iterative_refinement([[2.,0],[0,3]],[1,1],x0=[0.,0.],max_iter=0,tol=0); assert not r.converged
    F=lambda x:np.array([x[0]**2-1]); J=lambda x:np.array([[2*x[0]]]);r=numerics.newton_system(F,[2.],jac=J);assert r.converged
    with pytest.raises(SingularSystem): numerics.newton_system(lambda x:np.array([1.]),[0.],jac=lambda x:np.array([[0.]]),max_iter=2)

def test_autodiff_extended():
    x=autodiff.Dual(2,1)
    y=(3-x)+x*2+x/2+2/x+x**2-autodiff.cos(x)+autodiff.exp(autodiff.Dual(0,1))+autodiff.log(x)
    assert math.isfinite(y.val) and math.isfinite(y.der)
    f=lambda z:np.array([z[0]**2+z[1],z[0]*z[1]])
    v=autodiff.vjp(f,[1.,2.],[1.,.5]);assert v.shape==(2,)
    with pytest.raises(DimensionMismatch):autodiff.jvp(f,[1,2],[1])

def test_sparse_invalid_and_max_paths():
    with pytest.raises(DimensionMismatch): sparse.COO([0],[0,1],[1],(2,2))
    with pytest.raises(InvalidInput): sparse.COO([3],[0],[1],(2,2))
    with pytest.raises(DimensionMismatch): sparse.CSR([0,1],[0,1],[1],(1,1))
    A=sparse.as_csr([[2.,1.],[1.,2.]])
    with pytest.raises(DimensionMismatch):A.matvec([1])
    with pytest.raises(SingularSystem):sparse.jacobi_preconditioner([[0.,1.],[1.,2.]])
    with pytest.raises(InvalidInput): sparse.cg(A,[1,1],tol=0,max_iter=0)
    r=sparse.gmres(A,[1,1],tol=0,max_iter=1,restart=1);assert isinstance(r,SolverResult)
    with pytest.raises(ConvergenceFailure):sparse.cg(sparse.as_csr([[0.,1.],[1.,0.]]),[1,0],max_iter=3)

def test_optimization_fd_and_nonconverged():
    r=optimization.gradient_descent(lambda x:(x[0]-1)**2,[0.],grad=None,lr=.2,max_iter=100);assert r.converged
    r=optimization.bfgs(lambda x:(x[0]-1)**2,[0.],grad=None,max_iter=50);assert r.converged
    r=optimization.lbfgs(lambda x:(x[0]-1)**2,[0.],grad=None,max_iter=50,memory=2);assert r.converged
    r=optimization.gradient_descent(lambda x:(x[0]-10)**2,[0.],grad=lambda x:np.array([2*(x[0]-10)]),max_iter=0);assert not r.converged
    with pytest.raises(InvalidInput):optimization.projected_gradient(lambda x:x[0]**2,[0],[(1,-1)])
    assert optimization.constraint_violation([2],ineq=[lambda x:x[0]-1],eq=[lambda x:x[0]-2])==1

def test_ode_invalid_rejection_and_max():
    with pytest.raises(InvalidInput):ode.euler(lambda t,y:y,(1,0),[1],.1)
    with pytest.raises(InvalidInput):ode.euler(lambda t,y:y,(0,1),[1],0)
    # Tight tolerance forces rejections but converges.
    r=ode.rk45(lambda t,y:10*y,(0,.1),[1.],.1,rtol=1e-11,atol=1e-13);assert r.rejected>0 and r.accepted>0
    with pytest.raises(ConvergenceFailure):ode.rk45(lambda t,y:y,(0,1),[1.],.1,max_steps=1)

def test_pde_extra_paths():
    with pytest.raises(InvalidInput):pde.poisson_1d_dirichlet([1],[0,1])
    with pytest.raises(InvalidInput):pde.poisson_1d_dirichlet([1,1],[0,.2,1,2])
    u=pde.linear_advection_1d([0,1,0],-1,1,.5,2,False);assert len(u)==3
    with pytest.raises(CFLViolation):pde.linear_advection_1d([0,1,0],1,1,2,1)

def test_cfd_extra_paths():
    with pytest.raises(DimensionMismatch):cfd.primitive2d(np.ones((2,2,3)))
    U=np.zeros((2,2,4));U[...,0]=1;U[...,3]=-.1
    with pytest.raises(NonPhysicalState):cfd.primitive2d(U)
    rho=np.ones((3,3));z=np.zeros_like(rho);p=np.ones_like(rho);U=cfd.cons2d(rho,z,z,p)
    r=cfd.euler_2d_cartesian(U,.1,.1,.001,periodic=False);assert r.steps>0
    with pytest.raises(InvalidInput):cfd.euler_2d_cartesian(np.ones((1,1,4)),1,1,1)
    with pytest.raises(ConvergenceFailure):cfd.euler_2d_cartesian(U,.1,.1,.1,max_steps=0)
    with pytest.raises(DimensionMismatch):cfd.navier_stokes_viscous_flux_2d([1],[1],[1],1,1)

def test_fea_extra_paths():
    with pytest.raises(InvalidInput):fea.bar1d([0,1],[(0,1)],-1,1)
    with pytest.raises(DegenerateGeometry):fea.bar1d([0,0],[(0,1)],1,1)
    with pytest.raises(SingularSystem):fea.bar1d([0,1],[(0,1)],1,1,loads={1:1},fixed=[])
    with pytest.raises(DegenerateGeometry):fea.triangle3_plane_stress_stiffness([[0,0],[1,0],[2,0]],1,.3)
    with pytest.raises(DimensionMismatch):fea.assemble([([0,1],np.eye(3))],2)
    K=np.array([[2.,-1.],[-1.,1.]])
    r=fea.solve_linear(K,[0,1],prescribed={0:.5});assert r.solution[0]==.5
    with pytest.raises(DimensionMismatch):fea.solve_linear(np.eye(2),[1,2,3])

def test_geometry_extra_paths():
    assert geometry.segment_intersection([0,0],[1,0],[0,1],[1,1]) is None
    with pytest.raises(DegenerateGeometry):geometry.project_point_segment([0,0],[1,1],[1,1])
    q=geometry.plane_projection([1,2,3],[0,0,0],[0,0,1]);assert np.allclose(q,[1,2,0])
    lo,hi=geometry.aabb([[1,2],[3,-1]]);assert np.allclose(lo,[1,-1]) and np.allclose(hi,[3,2])
    assert geometry.triangle_area([0,0,0],[1,0,0],[0,1,0])==pytest.approx(.5)

def test_cad_invalid_paths():
    b=cad.BRepModel();v=b.add_vertex((0,0,0));e=b.add_edge(v,9);b.wires[0]=cad.Wire(0,[e]);b.faces[0]=cad.Face(0,99);b.shells[0]=cad.Shell(0,[9]);b.solids[0]=cad.Solid(0,[9]);res=b.validate();assert not res['valid'] and len(res['errors'])>=4
    with pytest.raises(InvalidInput):b.add_vertex((1,2))

def test_mesh_invalid_paths():
    with pytest.raises(DimensionMismatch):mesh.TriMesh([[0,0],[1,0],[0,1]],[[0,1]])
    with pytest.raises(InvalidInput):mesh.TriMesh([[0,0],[1,0],[0,1]],[[0,1,4]])
    with pytest.raises(InvalidInput):mesh.TriMesh([[0,0],[1,0],[0,1]],[[0,1,2],[2,1,0]])
    with pytest.raises(InvalidInput):mesh.rectangular_tri_mesh(0,1)

def test_multiphysics_extra_paths():
    with pytest.raises(InvalidInput):multiphysics.fixed_point_coupling(lambda x,y:x,lambda x,y:y,[0],[0],relaxation=2)
    r=multiphysics.fixed_point_coupling(lambda x,y:x+1,lambda x,y:y+1,[0],[0],max_iter=1,relaxation=1);assert not r.converged
    with pytest.raises(DimensionMismatch):multiphysics.conservative_transfer([1],[1,2],[1])
    with pytest.raises(InvalidInput):multiphysics.conservative_transfer([1],[1],[-1])

def test_digital_twin_extra_paths():
    with pytest.raises(DimensionMismatch):digital_twin.StateTwin(np.array([1,2]),np.eye(3))
    with pytest.raises(InvalidInput):digital_twin.StateTwin(np.array([1,2]),np.array([[1,2],[2,1]],float))
    tw=digital_twin.StateTwin(np.array([0.,0.]),np.eye(2));tw.predict(np.eye(2),control=[1],B=np.array([[1],[0]]));assert tw.state[0]==1
    with pytest.raises(InvalidInput):digital_twin.StateTwin(np.array([0.]),np.eye(1)).predict(np.eye(1),control=[1])
    tw=digital_twin.StateTwin(np.array([0.]),np.zeros((1,1)))
    with pytest.raises(SingularSystem):tw.update([1],[[1]],[[0.]])

def test_uq_stats_signal_extra_paths():
    with pytest.raises(InvalidInput):uq.latin_hypercube(0,2)
    one=uq.monte_carlo(lambda x:x,lambda rng:1.,1);assert one['std']==0
    with pytest.raises(InvalidInput):uq.sobol_first_order(lambda x:1.,[(0,1)],n=10)
    with pytest.raises(InvalidInput):stats.variance([1],ddof=1)
    with pytest.raises(DimensionMismatch):stats.covariance([1,2],[1])
    assert stats.quantile([1,2,3],.5)==2
    with pytest.raises(InvalidInput):signal.ifft([])
    with pytest.raises(InvalidInput):signal.lowpass_fft([1,2],10,6)
    assert signal.correlation([1,2],[1,2]).size==3

def test_graph_search_extra_paths():
    d,p=graph.dijkstra({'a':{'b':1}},'a');assert d['b']==1
    with pytest.raises(InvalidInput):graph.dijkstra({'a':{'b':-1}},'a')
    assert graph.path_from_prev({},'a','b') is None
    r=search.astar(0,lambda s:s==2,lambda s:[]);assert not r.converged
    with pytest.raises(InvalidInput):search.astar(0,lambda s:False,lambda s:[(1,-1)])
    a,root=search.mcts(0,lambda s:[],lambda s,a:s,lambda s:0,lambda s:True,iterations=2);assert a is None

def test_ml_extra_paths():
    with pytest.raises(InvalidInput):ml.softmax([np.nan])
    with pytest.raises(InvalidInput):ml.softmax([-np.inf,-np.inf])
    with pytest.raises(DimensionMismatch):ml.attention(np.eye(2),np.ones((3,4)),np.ones((3,2)))
    Q=np.eye(2);K=np.eye(2);V=np.eye(2)
    with pytest.raises(DimensionMismatch):ml.attention(Q,K,V,np.ones((3,3),bool))
    with pytest.raises(InvalidInput):ml.attention(Q,K,V,np.array([[0,0],[1,1]],bool))
    d=ml.Dense.init(2,3,seed=1);assert d.forward([[1,2]]).shape==(1,3);assert np.array_equal(ml.relu([-1,2]),[0,2]);assert ml.mse([1,2],[1,4])==2
    g=ml.numerical_gradient(lambda x:float(np.sum(x*x)),np.array([1.,2.]));assert np.allclose(g,[2,4],atol=1e-5)
    with pytest.raises(InvalidInput):ml.cosine_beta_schedule(0)

def test_hpc_benchmark_and_status():
    rows=hpc.benchmark_scaling(square,3,workers=(1,2),repeats=4,backend='thread');assert len(rows)==2 and rows[0]['speedup']==pytest.approx(1)
    assert isinstance(hpc.capability_matrix()['cpu_count'],(int,type(None)))

def test_validation_json_and_repro(tmp_path):
    r=validation.validate_close('a','b',[1],[1]);s=validation.to_json([r]);assert '"passed": true' in s
    assert reproducibility.sha256_bytes(b'abc')=='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    p=tmp_path/'x';p.write_bytes(b'abc');assert reproducibility.sha256_file(p)==reproducibility.sha256_bytes(b'abc')
    rng=reproducibility.deterministic_rng(4);assert np.allclose(rng.random(3),reproducibility.deterministic_rng(4).random(3))
    bad=[{'path':'x','bytes':99,'sha256':'0'}];assert not reproducibility.verify_manifest(tmp_path,bad)['passed']

def test_serialization_bad_schema(tmp_path):
    p=tmp_path/'bad.npz';np.savez(p,__meta__=np.array(json.dumps({'schema':'BAD','arrays':{}})))
    with pytest.raises(InvalidInput):serialization.load_state(p)

def test_registry_all_execute_or_callables():
    assert registry.registry_integrity()['passed']
    for name,fn in registry.REGISTRY.items():assert callable(fn)

def test_benchmark_module():
    r=benchmark.benchmark(sum,[1,2,3],repeats=2);assert r['result']==6 and r['repeats']==2 and r['peak_memory']>=0

def test_discovery_extra():
    with pytest.raises(InvalidInput):discovery.exhaustive_discovery([],lambda x:x)
    r=discovery.exhaustive_discovery(range(10),lambda x:-x,minimize=False,max_evals=3);assert r.evaluated==3
    p=discovery.expression_program_search([1],{'/':lambda a,b:a/b},2,max_depth=1);assert p['evaluated']>=1

def test_units_unknown():
    with pytest.raises(InvalidInput):units.Quantity(1,'foo').to('m')

def test_endurance_report(tmp_path):
    p=tmp_path/'e.json';r=endurance.run_endurance(.05,sample_interval=.01,report_path=p);assert p.exists() and json.loads(p.read_text())['passed']==r['passed']

def test_remaining_solver_termination_paths():
    r=numerics.iterative_refinement([[2.,.3],[.3,1.]], [1.,2.], x0=[0.,0.], tol=0., max_iter=1); assert isinstance(r,SolverResult)
    r=numerics.bisection(lambda x:x-.3,0,1,tol=0,max_iter=1); assert not r.converged
    r=numerics.secant(lambda x:x*x-2,1,2,tol=0,max_iter=1); assert not r.converged
    r=numerics.newton_scalar(lambda x:x**3-2*x+2,lambda x:3*x*x-2,1.,tol=0,max_iter=1,damping=True); assert isinstance(r,SolverResult)
    r=numerics.newton_scalar(lambda x:x+1,lambda x:1,0,tol=0,max_iter=0,damping=False); assert not r.converged
    r=numerics.brent(lambda x:0.,0,1,tol=0,max_iter=1); assert r.converged
    r=numerics.brent(lambda x:x*x-2,0,2,tol=0,max_iter=1); assert not r.converged
    r=numerics.newton_system(lambda x:np.array([x[0]+1]),[0.],tol=0,max_iter=0); assert not r.converged

def test_remaining_sparse_termination_paths():
    A=sparse.as_csr(np.array([[4.,1.,0.],[1.,3.,1.],[0.,1.,2.]]));b=np.array([1.,2.,4.])
    r=sparse.cg(A,b,tol=0,max_iter=1);assert not r.converged
    r=sparse.bicgstab(A,b,tol=0,max_iter=1);assert not r.converged
    with pytest.raises(InvalidInput):sparse.gmres(A,b,max_iter=0)
    with pytest.raises(InvalidInput):sparse.bicgstab(A,b,max_iter=0)

def test_branch_closure_misc():
    assert check_invariants(a=True)
    assert np.allclose(geometry.Point((1.,2.)).array(),[1,2])
    with pytest.raises(DimensionMismatch):geometry.orientation2d([0,0,0],[1,0,0],[0,1,0])
    assert geometry.segment_intersection([0,0],[1,0],[2,-1],[2,1]) is None
    p=discovery.expression_program_search([1.],{'bad':lambda a,b:float('inf')},2,max_depth=1);assert p['evaluated']==0
    rb=optimization.bfgs(lambda x:(x[0]-1)**2,[0.],grad=lambda x:np.array([2*(x[0]-1)]),max_iter=0,tol=0);assert not rb.converged
    rl=optimization.lbfgs(lambda x:(x[0]-1)**2,[0.],grad=lambda x:np.array([2*(x[0]-1)]),max_iter=0,tol=0);assert not rl.converged
    rp=optimization.projected_gradient(lambda x:(x[0]-1)**2,[0.],[(-5,5)],grad=lambda x:np.array([2*(x[0]-1)]),max_iter=0,tol=0);assert not rp.converged
