import os,tempfile,math,json
import numpy as np
from supermoon31.core import Quantity,UNIT,directional_derivative_check
from supermoon31.cad import CadKernel,BSplineCurve,NURBSCurve,Feature,ParametricModel,AssemblyNode
from supermoon31.mesh import tet_box,boundary_layer_total,first_layer_from_total,triangle_quality
from supermoon31.fea import truss2d,thermal_bar,j2_radial_return,penalty_contact,laminate_abd,newmark,modal,cst_stiffness,solve_tet4
from supermoon31.cfd import sod_initial,euler_1d,primitive,cavity_flow,y_plus,smagorinsky_nut
from supermoon31.multiphysics import aitken_fixed_point,conjugate_interface
from supermoon31.hpc import mixed_precision_refinement,roofline,checkpoint,restart,capability_matrix
from supermoon31.validation import rmse,mae,numerical_equivalent
from supermoon31.optimization import pareto_mask,latin_hypercube,sobol,robust_objective
from supermoon31.certification import Requirement,RequirementsDB,fault_tree,AuditChain
from supermoon31.digital_twin import KalmanTwin
from supermoon31.registry import technology_registry,mathematical_registry
from supermoon31.aircraft import parametric_wing,conservative_load_check

def test_units():
    assert ((2*UNIT['m'])+(3*UNIT['m'])).value==5
    try: _=UNIT['m']+UNIT['s']; assert False
    except ValueError: pass

def test_cad_primitives_and_boolean():
    k=CadKernel();a=k.box(1,1,1);b=k.cylinder(.2,1);c=k.difference(a,b);assert k.is_valid(c);assert 0<k.volume(c)<1

def test_step_roundtrip(tmp_path):
    k=CadKernel();a=k.box(1,2,3);p=tmp_path/'a.step';k.export_step(a,p);b=k.import_step(p);assert abs(k.volume(a)-k.volume(b))<1e-8

def test_iges_roundtrip(tmp_path):
    k=CadKernel();a=k.box(1,1,1);p=tmp_path/'a.igs';k.export_iges(a,p);b=k.import_iges(p);assert abs(k.volume(a)-k.volume(b))<1e-7

def test_heal_audit():
    k=CadKernel();a=k.box(1,1,1);b,audit=k.heal(a);assert audit['after']['valid'] and audit['geometry_delta']<1e-10

def test_bspline_nurbs():
    c=np.array([[0,0,0],[1,0,0],[1,1,0],[2,1,0]],float);kn=np.array([0,0,0,0,1,1,1,1],float);b=BSplineCurve(c,3,kn);n=NURBSCurve(c,3,kn,np.ones(4));assert np.allclose(b.evaluate(.4),n.evaluate(.4))

def test_parametric_dag():
    m=ParametricModel();m.add(Feature('a','box',{'x':1,'y':1,'z':1}));m.add(Feature('b','cylinder',{'r':.2,'h':1}));m.add(Feature('c','difference',{},['a','b']));s=m.rebuild();assert 'c' in s

def test_assembly_cycle_detection():
    a=AssemblyNode('a');b=AssemblyNode('b');a.add(b);assert a.validate();b.add(a)
    try:a.validate();assert False
    except ValueError:pass

def test_mesh():
    m=tet_box(1,1,1,1,1,1);assert len(m.cells['tet4'])==6;assert abs(first_layer_from_total(boundary_layer_total(.1,1.2,5),1.2,5)-.1)<1e-12

def test_cst_patch_properties():
    k,B,D,A=cst_stiffness([[0,0],[1,0],[0,1]],200e9,.3);assert np.allclose(k,k.T);assert np.linalg.eigvalsh(k)[-1]>0

def test_truss():
    r=truss2d([[0,0],[1,0],[1,1]],[(0,1),(1,2),(0,2)],200e9,1e-4,{5:-1000},[0,1,3]);assert r.residual_norm<1e-7

def test_tet_solver():
    m=tet_box(1,1,1,1,1,1); fixed=[]
    for i,p in enumerate(m.nodes):
        if abs(p[0])<1e-12:fixed.extend([3*i,3*i+1,3*i+2])
    load_node=int(np.argmax(m.nodes[:,0]+m.nodes[:,1]+m.nodes[:,2]));r=solve_tet4(m.nodes,m.cells['tet4'],1e7,.3,{3*load_node+2:-100},fixed);assert np.all(np.isfinite(r.u))

def test_thermal():
    x,T=thermal_bar(1,20,10,1,T0=0,T1=100);assert np.max(abs(T-100*x))<1e-10

def test_j2():
    s,ep,C,y=j2_radial_return([.01,0,0,0,0,0],np.zeros(6),0,200e9,.3,250e6,1e9);assert y and ep>0 and np.all(np.isfinite(s))

def test_contact():
    assert penalty_contact(.1,1e5)==(0,0);f,e=penalty_contact(-.01,1e5);assert f>0 and e>0

def test_laminate():
    p={'E1':130e9,'E2':10e9,'G12':5e9,'nu12':.3,'t':.000125};A,B,D=laminate_abd([{**p,'theta_deg':0},{**p,'theta_deg':90}]);assert np.all(np.linalg.eigvalsh(A)>0)

def test_modal_newmark():
    w,V=modal([[2,-1],[-1,2]],np.eye(2));assert np.all(w>0);u,v,a=newmark(np.eye(1),np.zeros((1,1)),np.ones((1,1)),np.array([1.]),.01,10);assert np.isfinite(u).all()

def test_euler_sod():
    x=np.linspace(0,1,100);r=euler_1d(x,sod_initial(x),.01,second_order=False);rho,u,p=primitive(r.U);assert np.all(rho>0) and np.all(p>0) and r.metadata['t']>=.01

def test_cavity():
    r=cavity_flow(17,17,100,dt=.001,steps=5,pressure_iterations=20);assert np.isfinite(r['u']).all() and len(r['divergence_history'])==5

def test_turbulence_utils(): assert y_plus(1.2,1,.001,1.8e-5)>0 and smagorinsky_nut(.17,.01,100)>0

def test_aitken():
    x,r=aitken_fixed_point(lambda z:.5*z+1,[0.],tol=1e-9);assert r['converged'] and abs(x[0]-2)<1e-7

def test_cht():
    r=conjugate_interface(2,4,100,0,1,1);assert 0<r['interface_temperature']<100

def test_mixed_precision():
    A=np.array([[4.,1.],[1.,3.]]);b=np.array([1.,2.]);x,h=mixed_precision_refinement(A,b);assert np.linalg.norm(A@x-b)<1e-8

def test_roofline(): assert roofline(1000,100,100,2)['ceiling']==20

def test_checkpoint(tmp_path):
    p=checkpoint(tmp_path/'c.npz',{'x':[1,2,3]});r=restart(p);assert np.all(r['x']==[1,2,3])

def test_validation(): assert rmse([1,2],[1,2])==0 and mae([1,2],[2,2])==.5 and numerical_equivalent([1],[1+1e-10])

def test_sampling(): assert latin_hypercube(8,3).shape==(8,3) and sobol(8,3).shape==(8,3) and robust_objective([1,2,3])>2

def test_pareto():
    m=pareto_mask([[1,1],[2,2],[.5,3]]);assert m.tolist()==[True,False,True]

def test_requirements():
    db=RequirementsDB();db.add(Requirement('A','A','shall','src',criticality='HIGH'));db.add(Requirement('B','B','shall','src'));db.link('A','B');assert not db.orphan_critical();assert not db.validate()

def test_fault_tree(): assert abs(fault_tree({'op':'OR','children':[.1,.2]})-.28)<1e-12

def test_audit():
    a=AuditChain();a.append('x','y',{},{});a.append('x','z',{},{});assert a.verify()

def test_kalman():
    k=KalmanTwin(np.array([0.]),np.eye(1),np.eye(1),np.eye(1),np.eye(1)*.01,np.eye(1)*.1);k.predict();k.update([1]);assert 0<k.x[0]<1

def test_registries(): assert len(technology_registry())>=450 and len(mathematical_registry())>=300

def test_aircraft_cad():
    w=parametric_wing(10,2,1);k=CadKernel();assert k.volume(w)>0

def test_load_conservation(): assert conservative_load_check([[1,0,0],[2,0,0]],[[3,0,0]])['pass']

def test_hpc_matrix_honest():
    m=capability_matrix();assert m['CPU']['available'] is True
from supermoon31.advanced import ConstraintSystem,newton_solve,euler_bernoulli_beam_stiffness,timoshenko_beam_stiffness,mindlin_plate_q4_stiffness,neo_hookean_first_piola,green_lagrange,von_mises,augmented_contact,mode_I_K,energy_release_rate,phase_field_energy_1d,hllc_flux,vof_advect_1d,level_set_reinitialize,arrhenius_rate,integrate_species,ale_flux,acoustic_fft,discrete_adjoint,form_linear

def test_constraint_system():
    c=ConstraintSystem(2).add(lambda x:[x[0]+x[1]-3]).add(lambda x:[x[0]-x[1]-1]);r=c.solve([0,0]);assert r['success'] and np.allclose(r['x'],[2,1]) and r['dof']==0

def test_newton():
    x,r=newton_solve(lambda x:[x[0]**2-2],lambda x:[[2*x[0]]],[1.]);assert r['converged'] and abs(x[0]-np.sqrt(2))<1e-9

def test_beam_elements():
    k=euler_bernoulli_beam_stiffness(200e9,1e-6,2);t=timoshenko_beam_stiffness(200e9,1e-6,80e9,1e-3,2);assert np.allclose(k,k.T) and np.allclose(t,t.T)

def test_mindlin_shell_kernel():
    k=mindlin_plate_q4_stiffness([[0,0],[1,0],[1,1],[0,1]],70e9,.3,.01);assert np.allclose(k,k.T) and np.isfinite(k).all()

def test_hyperelastic():
    F=np.diag([1.1,1,1]);P=neo_hookean_first_piola(F,1e6,2e6);assert P[0,0]>0 and green_lagrange(F)[0,0]>0

def test_vm_contact_fracture():
    assert von_mises([100,0,0,0,0,0])>0;assert augmented_contact(-.1,0,100)['active'];K=mode_I_K(100e6,.01);assert energy_release_rate(K,200e9)>0

def test_phase_field_energy(): assert phase_field_energy_1d([0,0.01],[0,.2],1e9,1000,.01,.1)>0

def test_hllc():
    from supermoon31.cfd import cons
    f=hllc_flux(cons(1.,0.,1.),cons(.125,0.,.1));assert np.isfinite(f).all()

def test_vof_levelset():
    a=np.r_[np.ones(5),np.zeros(5)];b=vof_advect_1d(a,1,.01,.1);assert np.all((b>=0)&(b<=1));p=level_set_reinitialize(np.linspace(-1,1,21),.1,3);assert np.isfinite(p).all()

def test_reaction():
    assert arrhenius_rate(1000,1e5,0,8e4)>0;sol=integrate_species([1,0],(0,1),[[-1,0],[1,0]]);assert sol.success and sol.y[0,-1]<1

def test_ale_acoustics():
    assert np.allclose(ale_flux([2,4],[1,1],1),[1,3]);f,A=acoustic_fft(np.sin(2*np.pi*5*np.linspace(0,1,101)[:-1]),.01);assert f[np.argmax(A)]==5

def test_adjoint():
    lam,g=discrete_adjoint([[2]],[1],[[3]],[4]);assert np.allclose(lam,[.5]) and np.allclose(g,[2.5])

def test_form_linear():
    r=form_linear([1],[[.25]],[1],0);assert r['beta']==2 and 0<r['pf']<.1
