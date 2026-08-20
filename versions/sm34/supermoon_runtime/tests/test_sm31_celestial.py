import json, math, hashlib
import numpy as np
import pytest

from supermoon31.core import convergence,condition_estimate,central_difference,directional_derivative_check,Status
from supermoon31.registry import technology_registry,mathematical_registry
from supermoon31.validation import observed_order,numerical_equivalent
from supermoon31.reproducibility import result_manifest,numerical_equivalence
from supermoon31.hpc import mixed_precision_refinement,checkpoint,restart,roofline
from supermoon31.multiphysics import aitken_fixed_point,conservative_scale,conjugate_interface
from supermoon31.optimization import pareto_mask,latin_hypercube,sobol,failure_probability
from supermoon31.digital_twin import KalmanTwin
from supermoon31.certification import fault_tree,AuditChain
from supermoon31.mesh import tet_box,boundary_layer_total,first_layer_from_total,Mesh
from supermoon31.fea import tet4_B,truss2d,newmark,elasticity_matrix
from supermoon31.cfd import cons,primitive,euler_1d,cfl
from supermoon31.advanced import newton_solve,form_linear,vof_advect_1d,hllc_flux,phase_field_energy_1d
from supermoon31.aircraft import aerodynamic_surrogate,conservative_load_check
from supermoon31.cad import Frame,Point3,BSplineCurve


def test_scope_frozen_exact_counts():
    assert len(technology_registry())==460
    assert len(mathematical_registry())==320
    assert len({x['id'] for x in technology_registry()})==460
    assert len({x['id'] for x in mathematical_registry()})==320

def test_explicit_failure_status_vocabulary():
    for x in ('INVALID_INPUT','NONCONVERGED','NUMERICAL_BREAKDOWN','UNAVAILABLE_BACKEND','UNQUALIFIED'):
        assert getattr(Status,x).value==x

def test_convergence_tolerance_semantics():
    assert convergence(1e-9,1.0,atol=1e-12,rtol=1e-8)
    assert not convergence(1e-7,1.0,atol=1e-12,rtol=1e-8)
    with pytest.raises(ValueError): convergence(1,1,atol=-1)

def test_condition_and_derivative_guards():
    assert condition_estimate(np.eye(3))==1.0
    with pytest.raises(ValueError): condition_estimate([[1,np.nan]])
    g=central_difference(lambda x: x[0]**2+x[1]**2,[1e6,2.0])
    assert np.allclose(g,[2e6,4],rtol=1e-5)

def test_directional_derivative_nonzero_direction():
    with pytest.raises(ValueError): directional_derivative_check(lambda x:float(x@x),lambda x:2*x,[1,2],[0,0])

def test_validation_rejects_zero_log_error():
    with pytest.raises(ValueError): observed_order([1,0],[.2,.1])
    assert not numerical_equivalent([1,np.nan],[1,2])

def test_manifest_is_canonical_for_arrays():
    a=result_manifest({'x':np.array([1.,2.])},{'y':np.array([3])},'s',{'rtol':1e-8})
    b=result_manifest({'x':np.array([1.,2.])},{'y':np.array([3])},'s',{'rtol':1e-8})
    assert a['input_hash']==b['input_hash'] and a['result_hash']==b['result_hash']

def test_equivalence_shape_truth():
    r=numerical_equivalence([1,2],[1])
    assert not r['pass'] and r['reason']=='shape_mismatch'

def test_mixed_precision_singular_breakdown():
    with pytest.raises(np.linalg.LinAlgError): mixed_precision_refinement([[1,1],[2,2]],[1,2])

def test_checkpoint_restart_equivalence(tmp_path):
    p=checkpoint(tmp_path/'x.npz',{'a':np.arange(5.),'b':np.eye(2)})
    x=restart(p)
    assert np.array_equal(x['a'],np.arange(5.)) and np.array_equal(x['b'],np.eye(2))

def test_roofline_domain_check():
    with pytest.raises(ValueError): roofline(1,0,10,10)

def test_aitken_reports_nonconvergence():
    x,info=aitken_fixed_point(lambda z:z+1,[0.],tol=1e-30,maxiter=3)
    assert not info['converged'] and info['status']=='NONCONVERGED'

def test_conservative_transfer_invariant():
    v=np.array([1.,3.]);ws=np.array([2.,1.]);wd=np.array([1.,4.,2.]);m=conservative_scale(v,ws,wd)
    assert abs(v@ws-m@wd)<1e-12

def test_conjugate_flux_balance():
    r=conjugate_interface(2,4,100,0,1,1)
    assert r['flux_balance_error']<1e-12

def test_pareto_duplicate_and_nan_semantics():
    assert pareto_mask([[1,1],[1,1],[2,2]]).tolist()==[True,True,False]
    with pytest.raises(ValueError): pareto_mask([[1,np.nan]])

def test_sampling_reproducible_seed():
    assert np.array_equal(latin_hypercube(8,2,7),latin_hypercube(8,2,7))
    assert np.array_equal(sobol(8,2,7),sobol(8,2,7))

def test_failure_probability_rejects_empty():
    with pytest.raises(ValueError): failure_probability([])

def test_kalman_covariance_remains_symmetric_psd():
    k=KalmanTwin(np.array([0.]),np.eye(1),np.eye(1),np.eye(1),np.eye(1)*.01,np.eye(1)*.1)
    k.predict();k.update([1.])
    assert np.allclose(k.P,k.P.T) and np.min(np.linalg.eigvalsh(k.P))>=-1e-12
    assert 'normalized_innovation_squared' in k.history[-1]

def test_fault_tree_probability_domain():
    assert abs(fault_tree({'op':'OR','children':[.1,.2]})-.28)<1e-12
    with pytest.raises(ValueError): fault_tree(1.2)

def test_audit_detects_tamper():
    a=AuditChain();a.append('u','op',{'x':1},{'y':2});assert a.verify();a.events[0]['output']['y']=3;assert not a.verify()

def test_mesh_generated_tets_are_positive():
    m=tet_box(1,1,1,2,2,2)
    for ids in m.cells['tet4']:
        X=m.nodes[ids];assert np.linalg.det(np.c_[X[1:]-X[0]])>0

def test_mesh_bad_connectivity_rejected():
    with pytest.raises(IndexError): Mesh(np.zeros((3,3)),{'tri3':[[0,1,9]]})

def test_boundary_layer_roundtrip():
    total=boundary_layer_total(.001,1.2,20);first=first_layer_from_total(total,1.2,20);assert abs(first-.001)<1e-14

def test_tet_degeneracy_rejected():
    with pytest.raises(ValueError): tet4_B([[0,0,0],[1,0,0],[0,1,0],[1,1,0]])

def test_truss_zero_length_rejected():
    with pytest.raises(ValueError): truss2d([[0,0],[0,0]],[(0,1)],1e9,1e-4)

def test_material_domain_rejected():
    with pytest.raises(ValueError): elasticity_matrix(1e9,.5)

def test_newmark_bad_mass_rejected():
    with pytest.raises(ValueError): newmark([[0]],[[0]],[[1]],[1],.1,1)

def test_cfd_invalid_primitive_rejected():
    with pytest.raises(FloatingPointError): primitive(np.array([[0.,0.,1.]]))

def test_cfd_uniform_grid_contract():
    x=np.array([0,.1,.25,.4]);U=cons(np.ones(4),np.zeros(4),np.ones(4))
    with pytest.raises(ValueError): euler_1d(x,U,.01)

def test_cfd_nonconvergence_explicit():
    x=np.linspace(0,1,40);U=cons(np.ones(40),np.zeros(40),np.ones(40))
    with pytest.raises(RuntimeError,match='NONCONVERGED'): euler_1d(x,U,1.0,max_steps=1,second_order=False)

def test_cfd_cfl_measured():
    U=cons(1.,0.,1.);assert cfl(U,.001,.1)>0

def test_newton_singular_breakdown():
    with pytest.raises(np.linalg.LinAlgError,match='NUMERICAL_BREAKDOWN'): newton_solve(lambda x:np.array([1.]),lambda x:np.array([[0.]]),[0.])

def test_form_covariance_validation():
    with pytest.raises(ValueError): form_linear([0],[[ -1 ]],[1],0)

def test_vof_cfl_guard():
    with pytest.raises(ValueError): vof_advect_1d([1,0],10,1,1)

def test_hllc_positivity_guard():
    with pytest.raises(FloatingPointError): hllc_flux([0,0,1],[1,0,2.5])

def test_phase_field_damage_bounds():
    with pytest.raises(ValueError): phase_field_energy_1d([0,1],[0,2],1,1,1,.1)

def test_aircraft_surrogate_domain():
    with pytest.raises(ValueError): aerodynamic_surrogate(10,0)

def test_load_conservation_reports_absolute_and_relative():
    r=conservative_load_check([[1,0,0]],[[1,0,0]])
    assert r['pass'] and r['absolute_force_error']==0

def test_frame_orthogonality_contract():
    with pytest.raises(ValueError): Frame(Point3(0,0,0),np.diag([1,1,2])).matrix()

def test_bspline_knot_monotonicity():
    with pytest.raises(ValueError): BSplineCurve(np.array([[0,0],[1,0],[2,0.]]),1,np.array([0,0,1,.5,1.]))
