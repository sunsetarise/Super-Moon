import warnings
import numpy as np
import pytest
from supermoon31 import cfd, cad, endurance, hpc, multiphysics, digital_twin, optimization, validation, aircraft, registry, core, certification


def _physical(U, gamma=1.4):
    r,u,p=cfd.primitive(U,gamma)
    assert np.all(np.isfinite(U))
    assert np.all(r>0)
    assert np.all(p>0)
    return r,u,p

@pytest.mark.parametrize('scheme',["rusanov","hll"])
def test_qp1_second_order_sod_regression(scheme):
    x=np.linspace(0,1,60); U0=cfd.sod_initial(x)
    out=cfd.euler_1d(x,U0,.2,scheme=scheme,second_order=True)
    assert out.U.shape==(60,3)
    _physical(out.U)
    assert out.metadata['status']=='CONVERGED_TO_T_END'
    assert out.metadata['CFL_observed_max']<=out.metadata['CFL_target']*(1+1e-12)


def test_qp1_reconstruction_contract_n_plus_one_faces():
    N=60;U=np.tile(cfd.cons(1.,0.,1.),(N,1));Ug=np.vstack([U[0],U[0],U,U[-1],U[-1]])
    UL,UR=cfd.reconstruct(Ug)
    assert UL.shape==UR.shape==(N+1,3)
    F=cfd.rusanov(UL,UR)
    assert F.shape==(N+1,3)
    assert (F[1:]-F[:-1]).shape==(N,3)


def test_qp1_uniform_state_preservation_both_orders():
    x=np.linspace(0,1,80); U0=np.tile(cfd.cons(1.1,.3,1.2),(len(x),1))
    for second_order in (False,True):
        out=cfd.euler_1d(x,U0,.05,second_order=second_order)
        assert np.allclose(out.U,U0,rtol=2e-13,atol=2e-13)


def test_qp1_second_order_is_not_first_order_bypass():
    x=np.linspace(0,1,100);U0=cfd.sod_initial(x)
    a=cfd.euler_1d(x,U0,.1,second_order=False).U
    b=cfd.euler_1d(x,U0,.1,second_order=True).U
    assert not np.allclose(a,b,rtol=1e-8,atol=1e-10)
    _physical(b)


def test_qp1_cfd_input_contract_edges():
    x=np.linspace(0,1,10);U=cfd.sod_initial(x)
    for kw in ({'cfl':0},{'cfl':1.1},{'gamma':1},{'max_steps':0},{'t_end':-1}):
        with pytest.raises(ValueError): cfd.euler_1d(x,U,kw.pop('t_end',.01),**kw)
    with pytest.raises(ValueError): cfd.euler_1d(x[::-1],U,.01)
    with pytest.raises(ValueError): cfd.euler_1d(np.r_[0,.1,.25,np.linspace(.4,1,7)],U,.01)
    with pytest.raises(ValueError): cfd.primitive(np.ones((4,2)))
    with pytest.raises(ValueError): cfd.primitive(np.array([[1.,0.,2.],[np.nan,0,2.]]))
    with pytest.raises(FloatingPointError): cfd.primitive(np.array([[0.,0.,1.]]))
    with pytest.raises(FloatingPointError): cfd.primitive(np.array([[1.,10.,1.]]))


def test_qp1_bspline_2d_curvature_warning_free():
    cp=np.array([[0.,0.],[1.,1.],[2.,0.]]) ; knots=np.array([0,0,0,1,1,1],float)
    b=cad.BSplineCurve(cp,2,knots)
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        k=b.curvature(.5)
    assert np.isfinite(k) and k>0


def test_qp1_bspline_curvature_3d_and_bad_dimension():
    knots=np.array([0,0,0,1,1,1],float)
    b3=cad.BSplineCurve(np.array([[0.,0.,0.],[1.,1.,0.],[2.,0.,0.]]),2,knots)
    assert np.isfinite(b3.curvature(.5))
    b1=cad.BSplineCurve(np.array([[0.],[1.],[2.]]),2,knots)
    with pytest.raises(ValueError): b1.curvature(.5)


def test_qp1_endurance_mixes_repaired_second_order():
    a=endurance.mixed_iteration(0); b=endurance.mixed_iteration(1)
    assert a['cfd_second_order'] is False and b['cfd_second_order'] is True
    assert a['linear_residual']<1e-7 and b['linear_residual']<1e-7
    assert a['fea_residual']<1e-6 and b['fea_residual']<1e-6


def test_qp1_short_endurance_report(tmp_path):
    p=tmp_path/'endurance.json';r=endurance.run_endurance(.05,p,.01)
    assert r['passed'] and r['iterations']>0 and not r['errors'] and not r['invariant_failures'] and p.exists()
    with pytest.raises(ValueError): endurance.run_endurance(0)
    with pytest.raises(ValueError): endurance.run_endurance(.1,sample_interval=0)


def test_qp1_hpc_guard_paths(tmp_path):
    A=np.eye(2);b=np.ones(2)
    with pytest.raises(ValueError): hpc.mixed_precision_refinement(np.array([[np.nan,0],[0,1]]),b)
    with pytest.raises(np.linalg.LinAlgError): hpc.mixed_precision_refinement(np.zeros((2,2)),b)
    with pytest.raises(ValueError): hpc.roofline(1,0,1,1)
    with pytest.raises(ValueError): hpc.roofline(np.inf,1,1,1)
    state={'x':np.arange(2)};p=hpc.checkpoint(tmp_path/'a.npz',state);assert np.array_equal(hpc.restart(p)['x'],state['x'])


def test_qp1_multiphysics_guard_paths():
    with pytest.raises(ValueError): multiphysics.aitken_fixed_point(lambda x:x,[0],tol=0)
    with pytest.raises(ValueError): multiphysics.nearest_transfer([[0,0]],[1],[[np.nan,0]])
    with pytest.raises(ValueError): multiphysics.conjugate_interface(1,1,np.nan,0,1,1)
    with pytest.raises(ValueError): multiphysics.conservative_scale([1,2],[1],[1])


def _twin():
    return digital_twin.KalmanTwin(np.zeros(2),np.eye(2),np.eye(2),np.eye(2),np.eye(2)*.01,np.eye(2)*.1)


def test_qp1_digital_twin_guard_paths():
    k=_twin();k.F=np.eye(3)
    with pytest.raises(ValueError): k.predict()
    k=_twin();k.H=np.ones((1,3))
    with pytest.raises(ValueError): k.predict()
    k=_twin();k.Q[0,0]=np.nan
    with pytest.raises(ValueError): k.predict()
    k=_twin()
    with pytest.raises(ValueError): k.predict(np.ones(2),np.ones((2,1)))
    with pytest.raises(ValueError): _twin().predict(np.array([np.nan]),np.ones((2,1)))
    with pytest.raises(ValueError): _twin().update([1,np.nan])


def test_qp1_optimizer_and_validation_edges():
    with pytest.raises(ValueError): optimization.pareto_mask([[1,np.nan]])
    with pytest.raises(ValueError): optimization.latin_hypercube(2,0)
    with pytest.raises(ValueError): optimization.sobol(0,2)
    with pytest.raises(ValueError): optimization.robust_objective([1,np.nan])
    with pytest.raises(ValueError): optimization.failure_probability([])
    with pytest.raises(ValueError): validation.rmse([1],[np.nan])


def test_qp1_aircraft_contracts_without_cad_backend_dependency():
    assert aircraft.aerodynamic_surrogate(20,50)['drag']>0
    with pytest.raises(ValueError): aircraft.aerodynamic_surrogate(0,50)
    with pytest.raises(ValueError): aircraft.optimize_wing(V=0)
    a=np.array([[1.,2.],[2.,3.]])
    assert aircraft.conservative_load_check(a,a)['pass']
    with pytest.raises(ValueError): aircraft.conservative_load_check([[1,2]],[[1,2,3]])


def test_qp1_certification_fault_and_audit_edges():
    for bad in (-.1,1.1,float('nan')):
        with pytest.raises(ValueError): certification.fault_tree(bad)
    ac=certification.AuditChain(); assert ac.verify()
    ac.events.append({'previous_hash':'0'*64})
    assert not ac.verify()


def test_qp1_core_extreme_scale_derivative_is_finite():
    x=np.array([1e12,1e-12])
    g=core.central_difference(lambda q: float(np.sum(q*q)),x)
    assert np.all(np.isfinite(g))
