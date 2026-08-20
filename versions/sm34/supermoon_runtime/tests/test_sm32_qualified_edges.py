import sys
import numpy as np
import pytest
from supermoon32.core import InvalidInput,DimensionMismatch,BackendUnavailable
from supermoon32.qualified import *

def test_risk_invalid_range():
    with pytest.raises(InvalidInput):RiskProfile(criticality=1.1)

def test_weights_invalid_keys_and_sum():
    with pytest.raises(InvalidInput):validate_weights({'criticality':1})
    w={k:0 for k in DEFAULT_WEIGHTS};w['criticality']=.5
    with pytest.raises(InvalidInput):validate_weights(w)

def test_cri_invalid():
    with pytest.raises(InvalidInput):classify_cri(-.1)

def test_scale_invalid():
    with pytest.raises(InvalidInput):classify_scale(-1)

def test_registry_duplicate():
    r=QualifiedToolRegistry();t=QualifiedTool('x','v');r.register(t)
    with pytest.raises(InvalidInput):r.register(t)

def test_adapter_executable_mismatch():
    t=QualifiedTool('x','v',executable='fakeexe');a=SubprocessToolAdapter(t)
    with pytest.raises(InvalidInput):a.validate_input([sys.executable,'-c','pass'])

def test_adapter_missing_executable():
    a=SubprocessToolAdapter(QualifiedTool('missing','v'))
    with pytest.raises(BackendUnavailable):a.execute(['/definitely/not/a/real/program'])

def test_dimension_mismatch():
    with pytest.raises(DimensionMismatch):EquationDimensionalCheck('bad',FORCE,PRESSURE).enforce()

def test_problem_invalid():
    with pytest.raises(InvalidInput):ProblemDefinition('','CFD',['e'],['u']).validate()
    with pytest.raises(InvalidInput):ProblemDefinition('x','CFD',[],['u']).validate()

def test_equation_graph_cycle():
    g=EquationGraph();g.add_dependency('a','b');g.add_dependency('b','a')
    with pytest.raises(InvalidInput):g.topological_order()

def test_regime_invalid():
    with pytest.raises(InvalidInput):detect_cfd_regime(-1,1)

def test_solver_bad_weights():
    s=SolverCandidate('a','x',True)
    with pytest.raises(InvalidInput):s.objective((1,2))

def test_route_no_candidates():
    with pytest.raises(InvalidInput):SolverRoutingEngine().route(RouteRequest('CFD',assess_risk(RiskProfile()),ScaleClass.S1_SMALL),[])

def test_order_invalid():
    with pytest.raises(InvalidInput):observed_order(0,1)
    with pytest.raises(InvalidInput):richardson_extrapolate(1,2,1,1)
    with pytest.raises(InvalidInput):grid_convergence_index(1,2,1,2)

def test_residual_invalid():
    with pytest.raises(InvalidInput):linear_residual([[1,2]],[1],[1])

def test_validation_invalid():
    with pytest.raises(InvalidInput):validation_metrics([1],[1,2])

def test_confidence_invalid_and_zero():
    with pytest.raises(InvalidInput):confidence_score(2,*([1]*7))
    s,c=confidence_score(0,*([1]*7));assert s==0 and c==ConfidenceClass.C0_UNASSESSED

def test_lhs_invalid():
    with pytest.raises(InvalidInput):transform_lhs_unit([[2]],[(0,1)])
    with pytest.raises(InvalidInput):lhs_samples(2,[(1,0)])

def test_sensitivity_invalid_method():
    with pytest.raises(InvalidInput):local_sensitivity(lambda x:0,[1],method='bad')

def test_reliability_invalid():
    with pytest.raises(InvalidInput):reliability_monte_carlo(lambda x:x,lambda r:1,0)

def test_robust_objective_invalid():
    with pytest.raises(InvalidInput):robust_objective(None,[])

def test_workflow_missing_dependency_and_cycle():
    g=WorkflowGraph();g.add(WorkflowNode('x',lambda **kw:1,('missing',)))
    with pytest.raises(InvalidInput):g.order()
    g2=WorkflowGraph();g2.add(WorkflowNode('a',lambda **kw:1,('b',)));g2.add(WorkflowNode('b',lambda **kw:1,('a',)))
    with pytest.raises(InvalidInput):g2.order()

def test_workflow_fail_no_retry():
    g=WorkflowGraph();g.add(WorkflowNode('x',lambda **kw:(_ for _ in ()).throw(RuntimeError('boom'))));out=g.execute();assert out['status']=='FAIL' and out['runs'][0].error.startswith('RuntimeError')

def test_factorial_empty():
    with pytest.raises(InvalidInput):factorial_sweep({'a':[]})

def test_experiment_invalid():
    with pytest.raises(InvalidInput):ExperimentPlan('',{}, {},'s',()).validate()

def test_provenance_invalid():
    g=ProvenanceGraph();
    with pytest.raises(InvalidInput):g.add_edge('x','y','z')

def test_evidence_duplicate():
    e=EvidenceEngine();r=EvidenceRecord('E','test','PASS');e.add_evidence(r)
    with pytest.raises(InvalidInput):e.add_evidence(r)

def test_mode_restrictions():
    with pytest.raises(InvalidInput):enforce_mode(WorkflowMode.PRODUCTION,True,True,True)
    with pytest.raises(InvalidInput):enforce_mode(WorkflowMode.PRODUCTION,False,False,True)
    with pytest.raises(InvalidInput):enforce_mode(WorkflowMode.PRODUCTION,False,True,False)

def test_hpc_gpu_candidate():
    r=route_hpc(1000,1e9,256,gpu_memory_bytes=1e9);assert r.backend=='GPU_CANDIDATE'

def test_scaling_invalid():
    with pytest.raises(InvalidInput):strong_scaling({2:1})
    with pytest.raises(InvalidInput):weak_scaling({1:-1})
    with pytest.raises(InvalidInput):load_imbalance([])

def test_multisolver_invalid():
    with pytest.raises(InvalidInput):compare_results([NormalizedResult('x','m',1,'A')])
    with pytest.raises(InvalidInput):compare_results([NormalizedResult('x','m',1,'A'),NormalizedResult('x','s',1,'B')])
    with pytest.raises(InvalidInput):compare_results([NormalizedResult('x','m',[1,2],'A'),NormalizedResult('x','m',[1],'B')])

def test_parameter_range_invalid():
    with pytest.raises(InvalidInput):ParameterRange(1,1)

def test_model_validity_quality_invalid():
    d=ModelValidityDomain('m')
    with pytest.raises(InvalidInput):d.assess({},2)

def test_error_budget_negative():
    with pytest.raises(InvalidInput):ErrorBudget(iteration=-1)

def test_surrogate_bad_input():
    with pytest.raises(InvalidInput):fit_polynomial_surrogate([[1,2]],[1,2])
    with pytest.raises(InvalidInput):fit_rbf([[1]],[1])
    with pytest.raises(InvalidInput):multifidelity_linear([1],[2])
    with pytest.raises(InvalidInput):select_max_uncertainty([[1],[2]],[1])

def test_qualification_bad_upgrade_via_downgrade():
    s=QualificationState('x',ClaimLevel.TESTED,'1')
    with pytest.raises(InvalidInput):s.downgrade(ClaimLevel.BENCHMARKED,'no')

def test_cosim_invalid_relaxation():
    with pytest.raises(InvalidInput):fixed_point_cosim(lambda b:b,lambda a:a,[0],[0],relaxation=0)

def test_transfer_bad_weights():
    with pytest.raises(InvalidInput):conservative_transfer_error([1,2],[3],[1],[1])

def test_physics_number_invalid():
    with pytest.raises(InvalidInput):reynolds(1,1,1,0)

def test_adjoint_invalid_and_singular():
    with pytest.raises(InvalidInput):adjoint_gradient([[1,2]],[1],[[1]],[1])
    with pytest.raises(Exception):adjoint_gradient([[0.]],[1.],[[1.]],[1.])

def test_pod_dmd_invalid():
    with pytest.raises(InvalidInput):pod_snapshots([],1)
    with pytest.raises(InvalidInput):dmd([[1],[2]])

def test_bayes_invalid():
    with pytest.raises(InvalidInput):bayesian_grid_calibration([],lambda x:0)

def test_mahalanobis_invalid():
    with pytest.raises(InvalidInput):mahalanobis([1,2],[[1]])

def test_optimization_governance_invalid():
    with pytest.raises(InvalidInput):pareto_nondominated([])
    with pytest.raises(InvalidInput):probabilistic_constraint([],1)
    with pytest.raises(InvalidInput):probabilistic_constraint([1],1,'bad')

def test_more_risk_and_scale_branches():
    assert decision_matrix(RiskClass.VERY_HIGH,ScaleClass.S2_WORKSTATION)['human_review']
    assert decision_matrix(RiskClass.MODERATE,ScaleClass.S2_WORKSTATION)['independent_verification']
    assert classify_scale(1000,distributed=True)==ScaleClass.S5_MULTI_NODE_HPC
    w=dict(DEFAULT_WEIGHTS);w['criticality']=-.1;w['impact']+=.1
    with pytest.raises(InvalidInput):validate_weights(w)

def test_routing_alternative_verifier_without_external():
    risk=RiskAssessment(.45,RiskClass.HIGH,False,(),True,False)
    c=[SolverCandidate('a','CFD',True,.1,verified_scale=ScaleClass.S2_WORKSTATION),SolverCandidate('b','CFD',True,.2,verified_scale=ScaleClass.S2_WORKSTATION)]
    d=SolverRoutingEngine().route(RouteRequest('CFD',risk,ScaleClass.S2_WORKSTATION),c);assert d.verification_solver in {'a','b'} and d.verification_solver!=d.primary

def test_cosim_nonconvergence_path():
    out=fixed_point_cosim(lambda b:b+1,lambda a:a+1,[0.],[0.],tol=1e-30,max_iter=2);assert not out.converged and out.iterations==2

def test_problem_extra_invalid_branches():
    with pytest.raises(InvalidInput):ProblemDefinition('x','',['e'],['u']).validate()
    with pytest.raises(InvalidInput):ProblemDefinition('x','CFD',['e'],[]).validate()
    g=EquationGraph()
    with pytest.raises(InvalidInput):g.add_node('')

def test_model_validity_missing_parameter_and_exclusive():
    d=ModelValidityDomain('m',{'x':ParameterRange(0,1,False)});a=d.assess({});assert 'missing:x' in a['violations'];assert not d.parameter_ranges['x'].contains(0)

def test_workflow_extra_branches():
    g=WorkflowGraph();g.add(WorkflowNode('x',lambda **kw:1))
    with pytest.raises(InvalidInput):g.add(WorkflowNode('x',lambda **kw:2))
    with pytest.raises(InvalidInput):WorkflowGraph().add(WorkflowNode('',lambda **kw:1))
    g2=WorkflowGraph();g2.add(WorkflowNode('bad',lambda **kw:(_ for _ in ()).throw(RuntimeError('x'))));g2.add(WorkflowNode('ok',lambda **kw:2));out=g2.execute(fail_fast=False);assert out['status']=='FAIL' and out['context']['ok']==2
    with pytest.raises(InvalidInput):ExperimentPlan('h',{}, {},'s',(),replications=0).validate()

def test_provenance_more_branches(tmp_path):
    p=tmp_path/'x';p.write_text('x');g=ProvenanceGraph();a=ArtifactRecord.from_file('a','x',p);g.add_artifact(a)
    with pytest.raises(InvalidInput):g.add_artifact(a)
    with pytest.raises(InvalidInput):g.trace_to('missing')

def test_evidence_more_branches():
    e=EvidenceEngine();
    with pytest.raises(InvalidInput):e.add_evidence(EvidenceRecord('','test','PASS'))
    c=ClaimRecord('C','x',ClaimLevel.IMPLEMENTED,[]);e.add_claim(c)
    with pytest.raises(InvalidInput):e.add_claim(c)
    assert e.to_dict()['claims']['C']['status']=='UNASSESSED'
    q=QualificationLedger();q.set(CapabilityQualification('x',MaturityLevel.M1_IMPLEMENTED,QualificationLevel.Q1_AVAILABLE));assert not q.require('x',maturity=MaturityLevel.M2_UNIT_TESTED);assert not q.require('x',qualification=QualificationLevel.Q2_TESTED)

def test_tools_more_branches():
    r=QualifiedToolRegistry()
    with pytest.raises(InvalidInput):r.register(QualifiedTool('','v'))
    t=QualifiedTool('x','v');r.register(t);r.register(QualifiedTool('x','v2'),replace=True);assert r.get('x').vendor_or_project=='v2' and r.as_dict()['x']['vendor_or_project']=='v2'
    with pytest.raises(InvalidInput):SubprocessToolAdapter(t).validate_input([])

def test_uq_more_invalid_branches():
    with pytest.raises(InvalidInput):transform_lhs_unit([1,2],[(0,1)])
    with pytest.raises(InvalidInput):local_sensitivity(lambda x:0,[[1]])

def test_research_math_more_branches():
    with pytest.raises(InvalidInput):adjoint_gradient(np.eye(2),[1,1],[[1],[2],[3]],[1])
    with pytest.raises(InvalidInput):pod_snapshots([[1,2],[3,4]],0)
    with pytest.raises(InvalidInput):dmd(np.zeros((2,3)),rank=2)
    with pytest.raises(InvalidInput):bayesian_grid_calibration([0,1],lambda x:-np.inf)
    with pytest.raises(Exception):mahalanobis([1,1],[[1,1],[1,1]])

def test_qualification_and_repro_extra():
    s=QualificationState('x',ClaimLevel.TESTED,'1');assert s.invalidate('x').valid is False
    assert not change_requires_requalification(QualificationState('x',ClaimLevel.TESTED,'1'),code_version='1')['required']
    ev=build_release_evidence([]);assert ev['artifacts']==[] and len(ev['manifest_sha256'])==64

def test_manager_invalid_args():
    with pytest.raises(InvalidInput):BenchmarkManager().run('x',lambda:1,repeats=0)
    with pytest.raises(InvalidInput):EnduranceManager().run(0,lambda i:1)

def test_endurance_manager_failure_paths():
    e=EnduranceManager(.005);r=e.run(.02,lambda i:(_ for _ in ()).throw(RuntimeError('x')) if i==0 else {'invariant_ok':False if i==1 else True});assert r['status']=='FAIL' and r['errors']>=1 and r['invariant_failures']>=1
