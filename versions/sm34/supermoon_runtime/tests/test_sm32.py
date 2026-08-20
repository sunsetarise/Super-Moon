import math, tempfile, os, json
import numpy as np
import pytest
from supermoon32 import core,numerics,sparse,optimization,ode,pde,cfd,fea,geometry,cad,mesh,multiphysics,digital_twin,uq,stats,signal,graph,search,ml,hpc,validation,reproducibility,serialization,registry,autodiff,units,discovery,endurance

def test_core_kahan_and_norm():
    x=[1e16,1.,-1e16]; assert core.kahan_sum(x) in (0.,1.)
    assert abs(core.stable_norm([3,4])-5)<1e-12
    assert np.allclose(core.safe_normalize([3,4]),[.6,.8])
    with pytest.raises(core.DegenerateGeometry):core.safe_normalize([0,0])
def test_core_poly_tol_invariant():
    assert core.stable_polyval([1,2,1],2)==9
    assert core.scale_aware_tolerance(1e9)>core.scale_aware_tolerance(1)
    with pytest.raises(core.InvariantViolation):core.check_invariants(a=True,b=False)
def test_lu_qr_cholesky():
    A=np.array([[4.,2.],[1.,3.]]);b=np.array([1.,2.]);x=numerics.lu_solve(A,b);assert np.allclose(A@x,b)
    Q,R=numerics.qr_householder(A);assert np.allclose(Q@R,A);assert np.allclose(Q.T@Q,np.eye(2))
    L=numerics.cholesky(A.T@A+np.eye(2));assert np.allclose(L@L.T,A.T@A+np.eye(2))
def test_linalg_more():
    A=np.array([[1.,2.],[3.,4.],[5.,6.]]);U,s,Vt=numerics.svd(A);assert np.allclose((U*s)@Vt,A)
    x,_,_,_=numerics.least_squares(A,np.array([1.,2.,3.]));assert x.shape==(2,)
    P=numerics.pseudoinverse(A);assert np.allclose(A@P@A,A)
    assert numerics.condition_estimate(np.eye(3))==pytest.approx(1.)
def test_iterative_refinement():
    A=np.array([[10.,2.],[2.,5.]]);b=np.array([3.,4.]);r=numerics.iterative_refinement(A,b);assert r.converged and np.linalg.norm(A@r.solution-b)<1e-10
def test_roots():
    f=lambda x:x*x-2
    assert numerics.bisection(f,0,2).solution==pytest.approx(math.sqrt(2),rel=1e-9)
    assert numerics.secant(f,1,2).solution==pytest.approx(math.sqrt(2),rel=1e-9)
    assert numerics.newton_scalar(f,lambda x:2*x,1).solution==pytest.approx(math.sqrt(2),rel=1e-9)
    assert numerics.brent(f,0,2).solution==pytest.approx(math.sqrt(2),rel=1e-9)
    with pytest.raises(core.InvalidInput):numerics.bisection(f,2,3)
def test_newton_system():
    F=lambda x:np.array([x[0]**2+x[1]-2,x[0]+x[1]**2-2])
    r=numerics.newton_system(F,[1.2,.8]);assert r.converged and np.linalg.norm(F(r.solution))<1e-8
    J=numerics.finite_difference_jacobian(F,[1.,1.]);assert J.shape==(2,2)
def test_sparse_formats():
    co=sparse.COO(np.array([0,0,1]),np.array([0,1,1]),np.array([2.,1.,3.]),(2,2));csr=co.to_csr();assert np.allclose(csr.to_dense(),co.to_dense());assert np.allclose(csr.matvec([1,2]),[4,6])
    cs=sparse.CSC.from_coo(co);assert np.allclose(cs.to_dense(),co.to_dense())
def test_sparse_solvers():
    A=np.diag([4.,5.,6.])+np.array([[0,1,0],[1,0,1],[0,1,0]],float);b=np.array([1.,2.,3.]);csr=sparse.as_csr(A)
    for fn in (sparse.cg,sparse.gmres,sparse.bicgstab):
        r=fn(csr,b,tol=1e-10,max_iter=100);assert r.converged and np.linalg.norm(A@r.solution-b)<1e-8
    M=sparse.jacobi_preconditioner(csr);assert M(b).shape==(3,)
def test_optimization_gradient_bfgs_lbfgs():
    f=lambda x:(x[0]-2)**2+3*(x[1]+1)**2;g=lambda x:np.array([2*(x[0]-2),6*(x[1]+1)])
    for fn in (optimization.gradient_descent,optimization.bfgs,optimization.lbfgs):
        kw={'lr':.1,'max_iter':1000} if fn is optimization.gradient_descent else {'max_iter':200}
        r=fn(f,[0,0],grad=g,tol=1e-7,**kw);assert r.converged and np.linalg.norm(r.solution-[2,-1])<1e-4
def test_optimization_constrained_derivative_free():
    f=lambda x:(x[0]-3)**2
    r=optimization.projected_gradient(f,[0.],[(-1,1)],lr=.1,tol=1e-8,max_iter=500);assert r.converged and r.solution[0]==pytest.approx(1.,abs=1e-5)
    p=optimization.penalty_optimize(lambda x:(x[0]-2)**2,[0.],ineq=[lambda x:x[0]-1],max_iter=100);assert p.diagnostics['constraint_violation']<1e-3
    n=optimization.nelder_mead(lambda x:(x[0]-1)**2+(x[1]+2)**2,[0,0],max_iter=500);assert n.converged and np.linalg.norm(n.solution-[1,-2])<1e-3
def test_ode_orders():
    f=lambda t,y:-y
    e=ode.euler(f,(0,1),[1.],.01);m=ode.midpoint(f,(0,1),[1.],.05);r=ode.rk4(f,(0,1),[1.],.1);exact=math.exp(-1)
    assert abs(e.y[-1,0]-exact)<.01;assert abs(m.y[-1,0]-exact)<1e-3;assert abs(r.y[-1,0]-exact)<1e-5
def test_rk45_event():
    r=ode.rk45(lambda t,y:-y,(0,2),[1.],.1,event=lambda t,y:y[0]-.5);assert abs(r.y[-1,0]-math.exp(-2))<1e-6;assert r.accepted>0 and r.events
def test_heat_and_poisson():
    u=np.sin(np.linspace(0,np.pi,21));h=pde.heat_1d_explicit(u,1.,np.pi/20,.0005,10,left=0,right=0);assert h.shape==(11,21);assert np.max(np.abs(h[-1]))<np.max(np.abs(h[0]))
    x=np.linspace(0,1,101);sol=pde.poisson_1d_dirichlet(lambda z:np.pi**2*np.sin(np.pi*z),x);assert np.max(np.abs(sol-np.sin(np.pi*x)))<2e-4
    with pytest.raises(core.CFLViolation):pde.heat_1d_explicit([0,1,0],1,1,.6,1)
def test_advection_mass():
    u=np.zeros(50);u[10:20]=1;v=pde.linear_advection_1d(u,1,1,.5,10,True);assert np.sum(v)==pytest.approx(np.sum(u))
def test_cfd2d_uniform_conservation():
    rho=np.ones((6,7));u=np.full_like(rho,.2);v=np.full_like(rho,-.1);p=np.ones_like(rho);U=cfd.cons2d(rho,u,v,p);r=cfd.euler_2d_cartesian(U,.1,.1,.01,periodic=True);assert r.min_density>0 and r.min_pressure>0 and max(r.conservation.values())<1e-10
    rr,uu,vv,pp=cfd.primitive2d(r.U);assert np.allclose(rr,1,atol=1e-10)
def test_viscous_flux():
    r=cfd.navier_stokes_viscous_flux_2d([1,2],[3,4],[5,6],1.5,.5);assert r['tau'].shape==(2,2);assert np.allclose(r['tau'],r['tau'].T);assert np.allclose(r['heat_flux'],[-2.5,-3])
def test_sm31_cfd_preserved():
    assert cfd.euler_1d is not None;x=np.linspace(0,1,40);r=cfd.euler_1d(x,cfd.sod_initial(x),.002,second_order=True);assert np.all(np.isfinite(r.U))
def test_bar1d_analytic():
    E=200e9;A=1e-4;F=1000.;r=fea.bar1d([0,2],[(0,1)],E,A,{1:F},[0]);assert r.displacement[1]==pytest.approx(F*2/(E*A));assert r.stress[0]==pytest.approx(F/A);assert r.residual_norm<1e-10
def test_fea_triangle_and_assembly():
    K,B,D,A=fea.triangle3_plane_stress_stiffness([[0,0],[1,0],[0,1]],210e9,.3,.01);assert np.allclose(K,K.T);assert A==pytest.approx(.5);Kg=fea.assemble([([0,1],np.array([[1,-1],[-1,1]],float))],2);assert np.allclose(Kg,[[1,-1],[-1,1]])
def test_fea_solve_linear():
    K=np.array([[1.,-1.],[-1.,1.]]);r=fea.solve_linear(K,[0.,1.],fixed=[0]);assert r.solution[1]==pytest.approx(1.)
def test_geometry_invariants():
    assert geometry.orientation2d([0,0],[1,0],[0,1])==1;assert geometry.orientation2d([0,0],[1,0],[2,0])==0
    q=geometry.segment_intersection([0,0],[1,1],[0,1],[1,0]);assert np.allclose(q,[.5,.5]);p,t,d=geometry.project_point_segment([.5,1],[0,0],[1,0]);assert np.allclose(p,[.5,0]) and t==.5 and d==1
    R=geometry.rotation_matrix_2d(.3);assert np.allclose(R.T@R,np.eye(2))
def test_cad_brep_and_bspline():
    b=cad.BRepModel();v0=b.add_vertex((0,0,0));v1=b.add_vertex((1,0,0));e=b.add_edge(v0,v1);b.wires[0]=cad.Wire(0,[e]);b.faces[0]=cad.Face(0,0);b.shells[0]=cad.Shell(0,[0]);b.solids[0]=cad.Solid(0,[0]);assert b.validate()['valid']
    assert cad.BSplineCurve is not None
    c=cad.BSplineCurve(np.array([[1.,0.],[1.,.5523],[.5523,1.],[0.,1.]]),3,np.array([0,0,0,0,1,1,1,1],float));assert math.isfinite(c.curvature(.5))
def test_mesh():
    m=mesh.rectangular_tri_mesh(3,2);v=m.validate();assert v['valid'] and len(m.boundary_edges())==10;assert len(m.adjacency())==12;assert np.all(m.quality()>0)
def test_multiphysics():
    r=multiphysics.fixed_point_coupling(lambda x,y:.5*(y+1),lambda x,y:.5*(x+1),[0.],[0.],tol=1e-8,max_iter=200,relaxation=.8);assert r.converged
    out,meta=multiphysics.conservative_transfer([1,2],[1,1],[.5,.5,1]);assert meta['error']<1e-12 and np.dot(out,[.5,.5,1])==pytest.approx(3)
def test_digital_twin():
    tw=digital_twin.StateTwin(np.array([0.,1.]),np.eye(2));tw.predict([[1,1],[0,1]],np.eye(2)*.01);u=tw.update([1.1],[[1,0]],[[.1]]);assert len(tw.history)==2 and u['innovation_norm']>=0 and np.all(np.linalg.eigvalsh(tw.covariance)>=-1e-10)
def test_uq():
    X=uq.latin_hypercube(100,3,3);assert X.shape==(100,3) and np.all((X>=0)&(X<=1))
    mc=uq.monte_carlo(lambda x:x,lambda rng:rng.normal(),500,seed=1);assert abs(mc['mean'])<.2
    bs=uq.bootstrap([1,2,3,4,5],n_resamples=200,seed=1);assert bs['ci95'][0]<3<bs['ci95'][1]
    S=uq.sobol_first_order(lambda x:x[0]+2*x[1],[(0,1),(0,1)],n=3000,seed=2);assert S[1]>S[0]
def test_stats():
    x=np.array([1.,2.,3.,4.]);assert stats.mean(x)==pytest.approx(2.5);assert stats.variance(x)==pytest.approx(np.var(x,ddof=1));assert stats.correlation(x,2*x)==pytest.approx(1.);assert stats.median(x)==2.5;assert stats.mad(x)>0
def test_signal():
    x=np.arange(8.,dtype=float);X=signal.fft(x);assert np.allclose(signal.ifft(X).real,x);assert signal.parseval_error(x)<1e-10;assert signal.convolution([1,2],[1,1]).tolist()==[1,3,2]
    t=np.arange(100)/100;y=np.sin(2*np.pi*5*t)+.5*np.sin(2*np.pi*30*t);f=signal.lowpass_fft(y,100,10);assert np.std(f-np.sin(2*np.pi*5*t))<1e-10
def test_graph():
    g={'a':{'b':1,'c':4},'b':{'c':2},'c':{}};assert graph.bfs(g,'a')[0]=='a';assert graph.dfs(g,'a')[0]=='a';d,p=graph.dijkstra(g,'a','c');assert d['c']==3 and graph.path_from_prev(p,'a','c')==['a','b','c'];assert len(graph.connected_components({'a':['b'],'b':['a'],'c':[]}))==2
def test_astar():
    goal=5;neighbors=lambda s:[(s+1,1)] if s<goal else [];r=search.astar(0,lambda s:s==goal,neighbors,lambda s:goal-s);assert r.converged and r.solution==list(range(6)) and r.diagnostics['cost']==5
def test_mcts():
    actions=lambda s:[1,2] if s<3 else [];transition=lambda s,a:s+a;terminal=lambda s:s>=3;reward=lambda s:1 if s==3 else 0;a,root=search.mcts(0,actions,transition,reward,terminal,iterations=300,seed=1);assert a in (1,2) and root.visits==300
def test_ml_attention():
    Q=np.eye(2);K=np.eye(2);V=np.array([[1.,0.],[0.,2.]]);o,w=ml.attention(Q,K,V);assert o.shape==(2,2);assert np.allclose(w.sum(axis=1),1)
    mask=np.array([[1,0],[1,1]],bool);o,w=ml.attention(Q,K,V,mask);assert w[0,1]==0
def test_ml_train_diffusion_q():
    X=np.arange(10.)[:,None];y=3*X[:,0]+2;r=ml.linear_regression_train(X,y,lr=.01,epochs=5000);assert abs(r['weights'][0]-3)<1e-2 and abs(r['bias']-2)<.1
    beta=ml.cosine_beta_schedule(100);assert len(beta)==100 and np.all((beta>0)&(beta<1))
    Q=np.zeros((2,2));td=ml.q_learning_step(Q,0,1,1,1);assert td==1 and Q[0,1]>0
def test_autodiff():
    d=autodiff.derivative(lambda x:autodiff.sin(x)*x*x,1.2);expected=math.cos(1.2)*1.2**2+2*1.2*math.sin(1.2);assert d==pytest.approx(expected,rel=1e-10)
    f=lambda x:np.array([x[0]**2+x[1],x[0]-x[1]**2]);j=autodiff.jvp(f,[1,2],[.5,-1]);eps=1e-6;fd=(f(np.array([1,2])+eps*np.array([.5,-1]))-f(np.array([1,2])-eps*np.array([.5,-1])))/(2*eps);assert np.allclose(j,fd,rtol=1e-5)
def test_units():
    assert units.Quantity(1000,'mm').to('m').value==pytest.approx(1);assert units.Quantity(180,'deg').to('rad').value==pytest.approx(math.pi)
    with pytest.raises(core.InvalidInput):units.Quantity(1,'m').to('kg')
def test_discovery():
    r=discovery.exhaustive_discovery(range(-5,6),lambda x:(x-2)**2);assert r.candidate==2 and r.score==0
    p=discovery.expression_program_search([1,2,3],{'+':lambda a,b:a+b,'*':lambda a,b:a*b},6,max_depth=1);assert p['error']==0
def test_hpc_status_thread():
    c=hpc.capability_matrix();assert c['serial']=='IMPLEMENTED' and c['threaded_cpu']=='IMPLEMENTED';assert hpc.threaded_map(lambda x:x*x,[1,2,3],2)==[1,4,9];assert 'available' in hpc.mpi_status() and 'available' in hpc.gpu_status()
def test_validation():
    r=validation.validate_close('x','case',[1,2],[1,2]);assert r.passed;assert validation.error_norms([1,2],[1,3])['Linf']==1;assert validation.observed_order(.1,.025)==pytest.approx(2)
    c=validation.conservation([1,2],[1,2.1]);assert c['max_absolute']==pytest.approx(.1)
def test_serialization_reproducibility(tmp_path):
    p=tmp_path/'s.npz';serialization.save_state(p,{'x':np.arange(5,dtype=float)},{'a':1});a,m=serialization.load_state(p);assert np.array_equal(a['x'],np.arange(5.));assert m['schema']=='SM32_STATE_V1'
    env=reproducibility.environment_fingerprint(1);assert 'python' in env and env['seed']==1
    root=tmp_path/'d';root.mkdir();(root/'a.txt').write_text('abc');man=reproducibility.manifest(root);assert reproducibility.verify_manifest(root,man)['passed']
def test_registry():
    r=registry.registry_integrity();assert r['passed'] and r['count']>=20;assert callable(registry.resolve('root.bisection'))
def test_endurance_mixed_iteration():
    r=endurance.mixed_iteration(1);assert not r['bad'] and r['cg_residual']<1e-7
def test_endurance_short():
    r=endurance.run_endurance(.2,sample_interval=.05);assert r['passed'] and r['iterations']>0 and r['errors']==0 and r['invariant_failures']==0
