import os, json, math
from pathlib import Path
import numpy as np
import pytest

from supermoon31 import core, validation, reproducibility, hpc, multiphysics, optimization, digital_twin, certification, mesh, fea, cfd, advanced, aircraft, cad


def test_core_io_quantity_provenance_and_environment(tmp_path):
    p=tmp_path/'a.bin'; p.write_bytes(b'abc')
    assert core.sha256_bytes(b'abc') == core.sha256_file(p)
    assert core.stable_json({'b':1,'a':2}) == '{"a":2,"b":1}'
    pr=core.Provenance(code_hash='x').finalized(); assert pr.timestamp>0 and len(pr.digest())==64
    q1=core.Quantity(2, core.UNIT['m'].dim); q2=core.Quantity(3, core.UNIT['m'].dim)
    assert (q1+q2).value==5 and (q2-q1).value==1
    assert (q1*2).value==4 and (2*q1).value==4 and (q1/2).value==1
    assert (q1*q2).dim[1]==2 and (q1/q2).dim==(0,0,0,0,0,0,0)
    with pytest.raises(ValueError): _=q1+core.Quantity(1)
    with pytest.raises(ValueError): core.condition_estimate([])
    with pytest.raises(ValueError): core.central_difference(lambda x:0,[1],h=0)
    vals=core.directional_derivative_check(lambda x:float(x@x),lambda x:2*x,[1.,2.])
    assert len(vals)==5
    with pytest.raises(ValueError): core.directional_derivative_check(lambda x:0,lambda x:np.ones(3),[1.,2.])
    with pytest.raises(ValueError): core.directional_derivative_check(lambda x:0,lambda x:np.ones(2),[1.,2.],eps=[0])
    env=core.environment_manifest(); assert 'python' in env and 'numpy' in env


def test_validation_full():
    assert validation.rmse([1,2],[1,3])==pytest.approx(1/math.sqrt(2))
    assert validation.mae([1,2],[1,3])==pytest.approx(.5)
    assert validation.relative_error(2,1)==1
    assert validation.observed_order([.25,.0625],[.5,.25])==pytest.approx(2)
    assert validation.richardson(1,.9,2,2)>1
    assert validation.numerical_equivalent([1],[1+1e-12])
    assert validation.conservation_error(10,9)==pytest.approx(.1)
    for bad in [([],[]),([1],[1,2]),([np.nan],[1])]:
        with pytest.raises(ValueError): validation.rmse(*bad)
    with pytest.raises(ValueError): validation.relative_error(1,1,0)
    with pytest.raises(ValueError): validation.observed_order([1],[1])
    with pytest.raises(ValueError): validation.observed_order([1,2],[1,1])
    with pytest.raises(ValueError): validation.richardson(1,2,1,1)
    assert not validation.numerical_equivalent([1],[1],rtol=-1)
    with pytest.raises(ValueError): validation.conservation_error(1,1,0)


def test_reproducibility_full(tmp_path):
    obj={'z':np.array([1.,2.]),'n':np.int64(3),'a':[True,None,1.2], 4:'x'}
    m=reproducibility.result_manifest(obj,{'r':np.array([[1]])},'solver',{'rtol':1e-8})
    assert m['canonicalization']=='SM31_CELESTIAL_JSON_V1'
    assert reproducibility.numerical_equivalence([],[])['pass']
    assert reproducibility.numerical_equivalence([1],[2],rtol=0,atol=.5)['pass'] is False
    assert reproducibility.numerical_equivalence([np.nan],[1])['reason']=='nonfinite'
    with pytest.raises(ValueError): reproducibility.numerical_equivalence([1],[1],atol=-1)
    with pytest.raises(ValueError): reproducibility.result_manifest({'x':float('inf')},{},'s',{})
    p=reproducibility.write_reproduction_pack(tmp_path/'pack')
    assert (p/'environment.json').exists() and (p/'environment.sha256').exists() and (p/'README.txt').exists()


def test_hpc_full(tmp_path):
    cap=hpc.capability_matrix(); assert 'CPU' in cap
    A=np.array([[4.,1.],[1.,3.]]); b=np.array([1.,2.])
    x,h=hpc.mixed_precision_refinement(A,b,maxiter=5,tol=1e-14); assert np.linalg.norm(A@x-b)<1e-9 and len(h)>=1
    x0,h0=hpc.mixed_precision_refinement(A,b,maxiter=0); assert x0.shape==(2,) and h0==[]
    with pytest.raises(ValueError): hpc.mixed_precision_refinement([[1,2,3]],[1])
    with pytest.raises(ValueError): hpc.mixed_precision_refinement(A,b,maxiter=-1)
    assert hpc.roofline(100,10,5,100)['classification']=='compute_bound'
    assert hpc.roofline(10,100,1000,1)['classification']=='bandwidth_bound'
    p=hpc.checkpoint(tmp_path/'cp.npz',{'x':np.arange(3),'m':np.eye(2)}); r=hpc.restart(p); assert np.array_equal(r['x'],np.arange(3))
    with pytest.raises(ValueError): hpc.checkpoint(tmp_path/'x',{})
    with pytest.raises(ValueError): hpc.checkpoint(tmp_path/'x',{'o':np.array([object()],dtype=object)})
    with pytest.raises(FileNotFoundError): hpc.restart(tmp_path/'missing')


def test_multiphysics_full():
    x,info=multiphysics.aitken_fixed_point(lambda z:.5*z+1,[0.],tol=1e-10,maxiter=100); assert info['converged'] and x[0]==pytest.approx(2,rel=1e-6)
    with pytest.raises(ValueError): multiphysics.aitken_fixed_point(lambda z:z,[],1e-3)
    with pytest.raises(FloatingPointError): multiphysics.aitken_fixed_point(lambda z:np.array([np.nan]),[0.],maxiter=2)
    with pytest.raises(ValueError): multiphysics.conservative_scale([1],[1],[1,-1])
    m=multiphysics.nearest_transfer([[0,0],[1,0]],[10,20],[[.1,0],[.9,0]]); assert m.tolist()==[10,20]
    with pytest.raises(ValueError): multiphysics.nearest_transfer([[0,0]],[1],[[0,0,0]])
    ci=multiphysics.conjugate_interface(1,2,100,0,1,1); assert ci['flux_balance_error']<1e-12
    with pytest.raises(ValueError): multiphysics.conjugate_interface(0,1,1,0,1,1)
    # legacy FSI partitioned path remains public
    out=multiphysics.fsi_partitioned(lambda d:np.asarray(d)*0, lambda f:np.asarray(f)*0, [1.], maxiter=3)
    assert len(out)==2


def test_optimization_full():
    r=optimization.optimize(lambda x:(x[0]-2)**2,[0.],bounds=[(-5,5)]); assert r.success and r.x[0]==pytest.approx(2,abs=1e-4)
    with pytest.raises(ValueError): optimization.optimize(lambda x:0,[])
    with pytest.raises(ValueError): optimization.optimize(lambda x:0,[1,2],bounds=[(0,1)])
    with pytest.raises(FloatingPointError): optimization.optimize(lambda x:np.nan,[0.])
    assert optimization.pareto_mask([[1,2],[2,1],[3,3]]).tolist()==[True,True,False]
    with pytest.raises(ValueError): optimization.pareto_mask([])
    assert optimization.latin_hypercube(4,3).shape==(4,3)
    assert optimization.sobol(5,2).shape==(5,2)
    for fn in (optimization.latin_hypercube,optimization.sobol):
        with pytest.raises(ValueError): fn(0,2)
    assert optimization.robust_objective([1,2,3],.5)>2
    with pytest.raises(ValueError): optimization.robust_objective([])
    assert optimization.failure_probability([-1,1,0])==pytest.approx(2/3)
    with pytest.raises(ValueError): optimization.failure_probability([np.nan])


def make_twin():
    return digital_twin.KalmanTwin(np.array([0.,0.]),np.eye(2),np.eye(2),np.eye(2),np.eye(2)*.01,np.eye(2)*.1)

def test_digital_twin_full():
    k=make_twin(); k.predict(np.array([1.]),np.array([[1.],[0.]])); assert k.x[0]==1
    k.update([1.,0.]); assert len(k.history)==1
    with pytest.raises(ValueError): make_twin().predict(np.array([1.]),None)
    k=make_twin(); k.P[0,0]=-1
    with pytest.raises(ValueError): k.predict()
    with pytest.raises(ValueError): make_twin().update([1.])
    k=make_twin(); k.R[:]=0; k.P[:]=0; k.Q[:]=0
    with pytest.raises(np.linalg.LinAlgError): k.update([0,0])


def test_certification_full():
    db=certification.RequirementsDB(); a=db.add(certification.Requirement('A','a','text',criticality='HIGH')); b=db.add(certification.Requirement('B','b','text'))
    assert db.orphan_critical()==['A']
    db.link('A','B'); assert db.orphan_critical()==[] and db.validate()==[]
    with pytest.raises(KeyError): db.add(certification.Requirement('A','x','x'))
    with pytest.raises(KeyError): db.link('A','X')
    c=certification.Requirement('C','c','',verification_method='BAD',status='BAD',parent='X',children=['X']);db.add(c)
    issues=db.validate(); assert len(issues)>=4
    db.links.append(('A','traces_to','B')); assert any('duplicate' in x[1] for x in db.validate())
    assert certification.fault_tree({'op':'AND','children':[.5,.2]})==pytest.approx(.1)
    assert certification.fault_tree({'op':'OR','children':[.5,.2]})==pytest.approx(.6)
    for bad in [2, {'op':'X','children':[.1]}, {'op':'AND','children':[]}]:
        with pytest.raises(ValueError): certification.fault_tree(bad)
    ac=certification.AuditChain(); e1=ac.append('u','op',{'a':1},{'b':2}); e2=ac.append('u','op2',{},{}); assert ac.verify() and e2['previous_hash']==e1['hash']
    with pytest.raises(ValueError): certification.AuditChain().append('','op',{}, {})
    ac.events[1]['previous_hash']='bad'; assert not ac.verify()


def test_mesh_full():
    assert mesh.line_mesh(1,2).cells['line2'].shape==(2,2)
    assert mesh.quad_mesh(1,2,2,2).cells['quad4'].shape==(4,4)
    assert mesh.tri_mesh(1,1,1,1).cells['tri3'].shape==(2,3)
    assert len(mesh.tet_box(1,1,1,1,1,1).cells['tet4'])==6
    assert mesh.triangle_quality([[0,0],[1,0],[0,1]])>0
    assert mesh.triangle_quality([[0,0],[0,0],[0,0]])==0
    assert mesh.tet_quality([[0,0,0],[1,0,0],[0,1,0],[0,0,1]])>0
    assert mesh.tet_quality(np.zeros((4,3)))==0
    a=mesh.boundary_layer(.001,1.0,3); assert np.allclose(a,.001)
    assert mesh.boundary_layer_total(.001,1,3)==pytest.approx(.003)
    assert mesh.first_layer_from_total(.003,1,3)==pytest.approx(.001)
    for call in [lambda:mesh.line_mesh(-1,2),lambda:mesh.quad_mesh(1,1,0,1),lambda:mesh.tri_mesh(1,np.nan,1,1),lambda:mesh.tet_box(1,1,0,1,1,1),lambda:mesh.boundary_layer(0,1,2),lambda:mesh.first_layer_from_total(-1,1,2)]:
        with pytest.raises(ValueError): call()
    with pytest.raises(ValueError): mesh.Mesh(np.array([[np.nan,0]]),{'line2':np.empty((0,2),int)})
    with pytest.raises(ValueError): mesh.Mesh(np.zeros((2,4)),{'x':np.empty((0,1),int)})


def tet_fixture():
    X=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    T=np.array([[0,1,2,3]])
    return X,T

def test_fea_full():
    C=fea.elasticity_matrix(210e9,.3); assert C.shape==(6,6)
    X,T=tet_fixture(); B,V=fea.tet4_B(X); assert B.shape==(6,12) and V>0
    r=fea.solve_tet4(X,T,210e9,.3,{9:1000.},[0,1,2,4,5,8]); assert np.isfinite(r.residual_norm)
    with pytest.raises(IndexError): fea.solve_tet4(X,[[0,1,2,9]],210e9,.3)
    with pytest.raises(IndexError): fea.solve_tet4(X,T,210e9,.3,{99:1},[0,1,2,4,5,8])
    tr=fea.truss2d([[0,0],[1,0],[1,1]],[(0,1),(1,2),(0,2)],200e9,1e-4,{5:-1000},[0,1,3]); assert tr.residual_norm<1e-6
    with pytest.raises(IndexError): fea.truss2d([[0,0],[1,0]],[(0,2)],1e9,1e-4)
    K,B,D,A=fea.cst_stiffness([[0,0],[1,0],[0,1]],200e9,.3,.1,True); assert K.shape==(6,6) and A>.4
    K2,*_=fea.cst_stiffness([[0,0],[1,0],[0,1]],200e9,.3,.1,False); assert K2.shape==(6,6)
    with pytest.raises(ValueError): fea.cst_stiffness([[0,0],[0,1],[1,0]],200e9,.3)
    u,v,a=fea.newmark([[1]],[[.1]],[[2]],[1.],.01,5,u0=[0.],v0=[0.]); assert u.shape==(6,1)
    u2,v2,a2=fea.newmark([[1]],[[0]],[[1]],lambda t:np.array([t]),.01,2); assert u2.shape==(3,1)
    w,V=fea.modal(np.diag([4.,9.]),np.eye(2),2); assert np.allclose(w,[2,3])
    with pytest.raises(ValueError): fea.modal([[1,2],[0,1]],np.eye(2),1)
    vals,vecs=fea.buckling(np.diag([2.,4.]),-np.eye(2),2); assert np.allclose(vals,[2,4])
    x,Tv=fea.thermal_bar(1,4,10,1,q=2,T0=0,T1=1); assert len(x)==5 and len(Tv)==5
    s,ep,C,took=fea.j2_radial_return(np.zeros(6),np.zeros(6),0,200e9,.3,250e6); assert not took
    s,ep,C,took=fea.j2_radial_return(np.array([.01,0,0,0,0,0]),np.zeros(6),0,200e9,.3,100e6); assert took
    assert fea.penalty_contact(1,100)==(0,0) and fea.penalty_contact(-.1,100)[0]>0
    ply={'E1':130e9,'E2':10e9,'G12':5e9,'nu12':.3,'t':.001,'theta_deg':45}; A,B,D=fea.laminate_abd([ply,ply]); assert A.shape==(3,3)
    with pytest.raises(ValueError): fea.laminate_abd([{'E1':1}])
    assert fea.richardson(1,1,2,2)['status']=='INDETERMINATE_ZERO_DIFFERENCE'
    assert fea.richardson(1,2,1,2)['status']=='NON_MONOTONIC'
    rr=fea.richardson(1,.5,.25,2); assert rr['status']=='OK'


def test_cfd_full():
    U=cfd.cons(np.array([1.,.8]),np.array([0.,1.]),np.array([1.,.5])); r,u,p=cfd.primitive(U); assert np.allclose(r,[1,.8])
    assert cfd.flux(U).shape==(2,3) and cfd.rusanov(U,U).shape==(2,3) and cfd.hll(U,U).shape==(2,3)
    with pytest.raises(ValueError): cfd.cons([1,2],[1,2,3],[1,1])
    with pytest.raises(ValueError): cfd.cons(0,0,1)
    with pytest.raises(FloatingPointError): cfd.primitive(np.array([1.,100.,1.]))
    Ug=np.tile(cfd.cons(1.,0.,1.),(6,1)); UL,UR=cfd.reconstruct(Ug); assert UL.shape==(3,3)
    with pytest.raises(ValueError): cfd.reconstruct(np.zeros((3,3)))
    x=np.linspace(0,1,60); U0=cfd.sod_initial(x)
    rso=cfd.euler_1d(x,U0,.001,scheme='rusanov',second_order=True); assert rso.metadata['status']=='CONVERGED_TO_T_END' and rso.U.shape==U0.shape
    rr,uu,pp=cfd.primitive(rso.U); assert np.all(rr>0) and np.all(pp>0) and np.all(np.isfinite(rso.U))
    r1=cfd.euler_1d(x,U0,.001,scheme='rusanov',second_order=False); assert r1.metadata['status']=='CONVERGED_TO_T_END'
    r2=cfd.euler_1d(x,U0,.001,scheme='hll',second_order=False); assert r2.metadata['status']=='CONVERGED_TO_T_END'
    r0=cfd.euler_1d(x,U0,0); assert r0.metadata['steps']==0
    with pytest.raises(ValueError): cfd.euler_1d(x,U0,.1,scheme='bad')
    cav=cfd.cavity_flow(7,7,100,.001,steps=2,pressure_iterations=3); assert cav['metadata']['steps']==2
    cav0=cfd.cavity_flow(5,5,100,.001,steps=0,pressure_iterations=1); assert cav0['metadata']['final_divergence_norm']==0
    assert cfd.sutherland_mu(300)>0 and cfd.y_plus(1,1,.001,1e-5)>0 and cfd.first_cell_height(1,1,1,1)==1
    assert cfd.smagorinsky_nut(.1,.2,3)>0 and cfd.wale_nut(.5,.1,1,2)>=0 and cfd.k_epsilon_nut(1,2,3)>0 and cfd.k_omega_nut(1,2,3)>0 and cfd.sst_blend(.5,2,4)==3
    assert len(cfd.boundary_layer_layers(.001,1.2,4))==4 and cfd.cfl(cfd.cons(1.,0.,1.),.01,.1)>0
    with pytest.raises(ValueError): cfd.sutherland_mu(0)
    with pytest.raises(ValueError): cfd.y_plus(1,1,1,0)
    with pytest.raises(ValueError): cfd.first_cell_height(0,1,1,1)
    with pytest.raises(ValueError): cfd.cfl(cfd.cons(1.,0.,1.),-1,.1)


def test_advanced_constraint_newton_and_continuation():
    cs=advanced.ConstraintSystem(1); cs.add(lambda x:x-2,'eq'); out=cs.solve([0.]); assert out['success'] and out['x'][0]==pytest.approx(2)
    with pytest.raises(ValueError): advanced.ConstraintSystem(1).solve([0.])
    with pytest.raises(ValueError): cs.solve([0.],xtol=0)
    x,info=advanced.newton_solve(lambda x:np.array([x[0]**2-2]),lambda x:np.array([[2*x[0]]]),[1.]); assert info['converged'] and x[0]==pytest.approx(math.sqrt(2))
    x,info=advanced.newton_solve(lambda x:np.array([1.]),lambda x:np.array([[1.]]),[0.],maxiter=2,line_search=False); assert info['status']=='NONCONVERGED_MAXITER'
    x,info=advanced.newton_solve(lambda x:np.array([1.]),lambda x:np.array([[1.]]),[0.],maxiter=2,line_search=True); assert info['status']=='NONCONVERGED_LINE_SEARCH'
    with pytest.raises(ValueError): advanced.newton_solve(lambda x:np.array([1.]),lambda x:np.eye(2),[0.])
    with pytest.raises(FloatingPointError): advanced.newton_solve(lambda x:np.array([np.nan]),lambda x:np.array([[1.]]),[0.])
    path=advanced.continuation([0,.5,1],lambda lam,x:(x+lam,{'converged':lam<1}),[0.]); assert len(path)==3
    with pytest.raises(ValueError): advanced.continuation([1,0],lambda l,x:(x,{'converged':True}),[0])


def test_advanced_mechanics_physics_and_reliability():
    assert advanced.euler_bernoulli_beam_stiffness(200e9,1e-6,2).shape==(4,4)
    assert advanced.timoshenko_beam_stiffness(200e9,1e-6,80e9,.01,2).shape==(4,4)
    with pytest.raises(ValueError): advanced.euler_bernoulli_beam_stiffness(0,1,1)
    K=advanced.mindlin_plate_q4_stiffness([[0,0],[1,0],[1,1],[0,1]],200e9,.3,.01); assert K.shape==(12,12)
    with pytest.raises(ValueError): advanced.mindlin_plate_q4_stiffness([[0,0],[0,1],[1,1],[1,0]],200e9,.3,.01)
    P=advanced.neo_hookean_first_piola(np.eye(3)*1.1,1.,1.); assert P.shape==(3,3)
    with pytest.raises(ValueError): advanced.neo_hookean_first_piola(np.diag([1,1,-1]),1,1)
    assert np.allclose(advanced.green_lagrange(np.eye(2)),0)
    assert advanced.von_mises([1,1,1,0,0,0])==pytest.approx(0)
    ac=advanced.augmented_contact(-.1,0,100); assert ac['active']
    assert advanced.coulomb_limit(-10,.3)==3
    assert advanced.mode_I_K(100,1)>0 and advanced.energy_release_rate(2,10)==.4
    assert advanced.energy_release_rate(2,10,.3,True)<.4
    e=advanced.phase_field_energy_1d([0,1,2],[0,.2,.5],1,1,.1,1); assert e>0
    for fn,args in [(advanced.coulomb_limit,(1,-1)),(advanced.mode_I_K,(1,0)),(advanced.energy_release_rate,(1,0)),(advanced.phase_field_energy_1d,([0,1],[0,2],1,1,1,1))]:
        with pytest.raises(ValueError): fn(*args)
    UL=np.array([1.,3.,10.]); UR=np.array([.8,2.,8.]); assert advanced.hllc_flux(UL,UR).shape==(3,)
    UL2=np.array([1.,-3.,10.]); UR2=np.array([.8,-2.,8.]); assert advanced.hllc_flux(UL2,UR2).shape==(3,)
    assert np.all((advanced.vof_advect_1d([1,.5,0],1,.1,1)>=0)); assert np.all((advanced.vof_advect_1d([1,.5,0],-1,.1,1)>=0))
    phi=advanced.level_set_reinitialize([-1,-.2,.1,.5,1],.1,steps=2); assert np.all(np.isfinite(phi))
    assert advanced.arrhenius_rate(300,1e3,0,1000)>0
    sol=advanced.integrate_species([1,0],[0,1],[[-1,0],[1,0]]); assert sol.success
    assert np.allclose(advanced.ale_flux([1,2],[.5,1],2),[0,0])
    f,A=advanced.acoustic_fft(np.sin(np.linspace(0,2*np.pi,64)),.01); assert len(f)==len(A)
    lam,grad=advanced.discrete_adjoint(np.eye(2),[1,2],np.eye(2),[3,4]); assert np.allclose(lam,[1,2]) and np.allclose(grad,[2,2])
    form=advanced.form_linear([0,0],np.eye(2),[1,0],1); assert form['sigma_g']==pytest.approx(1)
    with pytest.raises(ValueError): advanced.arrhenius_rate(0,1,0,1)
    with pytest.raises(ValueError): advanced.integrate_species([1],[1,0],[[1]])
    with pytest.raises(ValueError): advanced.ale_flux([1],[1,2],0)
    with pytest.raises(ValueError): advanced.acoustic_fft([1],1)
    with pytest.raises(np.linalg.LinAlgError): advanced.discrete_adjoint([[0]],[1],[[1]],[1])
    with pytest.raises(ValueError): advanced.form_linear([0],[[-1]],[1],0)
    with pytest.raises(ValueError): advanced.form_linear([0],[[0]],[1],0)


def test_cad_geometry_parametric_assembly_and_io(tmp_path):
    p=cad.Point3(1,2,3); assert np.allclose(p.array(),[1,2,3])
    v=cad.Vector3(3,0,0); assert v.norm()==3 and v.unit().x==1
    with pytest.raises(ValueError): cad.Vector3(0,0,0).unit()
    fr=cad.Frame(cad.Point3(1,0,0),np.eye(3)); assert np.allclose(fr.matrix()[:3,3],[1,0,0]) and fr.transform(cad.Point3(1,0,0)).x==2
    with pytest.raises(ValueError): cad.Frame(cad.Point3(0,0,0),np.diag([1,1,-1])).matrix()
    cp=np.array([[0.,0.],[1.,1.],[2.,0.]]) ; knots=np.array([0,0,0,1,1,1],float)
    b=cad.BSplineCurve(cp,2,knots); assert b.evaluate(.5).shape==(2,) and b.derivative(.5).shape==(2,) and np.isfinite(b.curvature(.5))
    n=cad.NURBSCurve(cp,2,knots,np.array([1.,2.,1.])); assert n.evaluate(.5).shape==(2,)
    with pytest.raises(ValueError): cad.NURBSCurve(cp,2,knots,np.array([0.,0.,0.]))
    k=cad.CadKernel(); box=k.box(1,2,3,'b'); cyl=k.cylinder(.2,3,'c'); sph=k.sphere(.5,'s'); tor=k.torus(1,.1,'t')
    assert k.volume(box)>0 and k.area(box)>0 and len(k.bounding_box(box))==6 and k.center_of_mass(box).shape==(3,) and k.is_valid(box)
    u=k.union(box,cyl); d=k.difference(box,cyl); inter=k.intersection(box,cyl); assert all(isinstance(x,cad.ShapeRecord) for x in (u,d,inter))
    with pytest.raises(ValueError): k.box(0,1,1)
    healed,audit=k.heal(box); assert audit['status']=='VALID'
    with pytest.raises(ValueError): k.heal(box,0)
    step=k.export_step(box,tmp_path/'x.step'); imp=k.import_step(step); assert k.is_valid(imp)
    if cad.OCP_IGES_AVAILABLE:
        ig=k.export_iges(box,tmp_path/'x.iges'); imp2=k.import_iges(ig); assert imp2 is not None
    model=cad.ParametricModel(k); model.add(cad.Feature('a','box',{'x':1,'y':1,'z':1})); model.add(cad.Feature('b','cylinder',{'r':.2,'h':1})); model.add(cad.Feature('u','union',{},['a','b'])); shapes=model.rebuild(); assert set(shapes)=={'a','b','u'}
    with pytest.raises(KeyError): model.add(cad.Feature('a','box',{}))
    bad=cad.ParametricModel(k); bad.add(cad.Feature('x','nope',{}));
    with pytest.raises(NotImplementedError): bad.rebuild()
    cyc=cad.ParametricModel(k); cyc.add(cad.Feature('a','box',{'x':1,'y':1,'z':1},['b']));cyc.add(cad.Feature('b','box',{'x':1,'y':1,'z':1},['a']))
    with pytest.raises(ValueError): cyc._order()
    root=cad.AssemblyNode('r'); child=root.add(cad.AssemblyNode('c')); assert root.validate()
    child.transform=np.ones((4,4));
    with pytest.raises(ValueError): root.validate()
    a=cad.AssemblyNode('a'); bb=cad.AssemblyNode('b'); a.children=[bb]; bb.children=[a]
    with pytest.raises(ValueError): a.validate()


def test_aircraft_full():
    a=aircraft.aerodynamic_surrogate(30,100); assert a['AR']==9 and a['dynamic_pressure']>0
    r=aircraft.optimize_wing(); assert r.success
    w=aircraft.parametric_wing(10,2,1,.1); assert w.semantic_id=='wing.reference'
    with pytest.raises(ValueError): aircraft.parametric_wing(-1,1,1,.1)
    with pytest.raises(ValueError): aircraft.optimize_wing(V=0)
    chk=aircraft.conservative_load_check([[1,2,3],[0,0,0]],[[.5,1,1.5],[.5,1,1.5]]); assert chk['pass']
    with pytest.raises(ValueError): aircraft.conservative_load_check([[1,2]],[[1,2,3]])
    with pytest.raises(ValueError): aircraft.conservative_load_check([[1,2]],[[1,2]],tol=-1)


def test_endurance_short_and_guards(tmp_path):
    from supermoon31 import endurance
    t=endurance.telemetry(); assert 'time' in t and 'threads' in t
    mi=endurance.mixed_iteration(1); assert mi['linear_residual']<1e-7 and mi['fea_residual']<1e-6 and mi['cfd_steps']>=1
    rp=tmp_path/'endurance.json'; r=endurance.run_endurance(.25,rp,sample_interval=.05); assert r['passed'] and r['iterations']>0 and rp.exists()
    with pytest.raises(ValueError): endurance.run_endurance(0)
    with pytest.raises(ValueError): endurance.run_endurance(1,sample_interval=0)
