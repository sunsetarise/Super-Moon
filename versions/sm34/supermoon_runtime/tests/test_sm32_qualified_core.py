import math,sys,json
from pathlib import Path
import numpy as np
import pytest

from supermoon32.core import InvalidInput,DimensionMismatch
from supermoon32.qualified import *

@pytest.mark.parametrize('cri,expected',[(0.0,RiskClass.LOW),(0.2,RiskClass.MODERATE),(0.4,RiskClass.HIGH),(0.6,RiskClass.VERY_HIGH),(0.8,RiskClass.CRITICAL),(1.0,RiskClass.CRITICAL)])
def test_classify_cri(cri,expected): assert classify_cri(cri) is expected

def test_risk_profile_and_assessment_low():
    p=RiskProfile(.1,.1,.1,.1,.1,.1,.1);a=assess_risk(p);assert 0<=a.cri<.2 and not a.mandatory_external_tool

def test_risk_mandatory_trigger():
    a=assess_risk(RiskProfile(triggers=frozenset({'airworthiness'})));assert a.mandatory_external_tool and a.required_human_review and 'airworthiness' in a.mandatory_reasons

def test_risk_high_independent_verification():
    p=RiskProfile(criticality=.9,impact=.9,evidence_deficiency=.8,qualification_deficiency=.9);a=assess_risk(p);assert a.required_independent_verification

def test_weights_valid(): assert abs(sum(validate_weights().values())-1)<1e-12

def test_scale_classes():
    assert classify_scale(10)==ScaleClass.S0_TOY
    assert classify_scale(1e3)==ScaleClass.S1_SMALL
    assert classify_scale(1e5)==ScaleClass.S2_WORKSTATION
    assert classify_scale(2e6)==ScaleClass.S3_MULTICORE_WORKSTATION
    assert classify_scale(2e7)==ScaleClass.S4_SINGLE_NODE_HPC
    assert classify_scale(2e7,distributed=True)==ScaleClass.S6_LARGE_DISTRIBUTED
    assert classify_scale(1e9)==ScaleClass.S7_EXTREME_DISTRIBUTED

def test_decision_matrix():
    assert decision_matrix(RiskClass.CRITICAL,ScaleClass.S2_WORKSTATION)['external_tool']=='MANDATORY'
    assert decision_matrix(RiskClass.LOW,ScaleClass.S7_EXTREME_DISTRIBUTED)['external_tool']=='MANDATORY_FOR_SCALE'
    assert decision_matrix(RiskClass.HIGH,ScaleClass.S2_WORKSTATION)['independent_verification']
    assert not decision_matrix(RiskClass.LOW,ScaleClass.S1_SMALL)['independent_verification']

def make_tool(name='ToolA',q=QualificationLevel.Q3_BENCHMARKED,domain='CFD'):
    return QualifiedTool(name,'TestVendor','1.0',(domain,),('solver',),qualification_level=q,validation_evidence=('V1',),benchmark_evidence=('B1',),executable=sys.executable if name=='PythonTool' else None)

def test_tool_registry_selection():
    r=QualifiedToolRegistry();r.register(make_tool('low',QualificationLevel.Q2_TESTED));r.register(make_tool('high',QualificationLevel.Q4_INDUSTRIALLY_VALIDATED));assert r.best('CFD',QualificationLevel.Q3_BENCHMARKED).tool_name=='high'

def test_tool_registry_domain_filter():
    r=QualifiedToolRegistry();r.register(make_tool('fea',domain='FEA'));assert r.best('CFD') is None and r.get('FEA').tool_name=='fea'

def test_subprocess_tool_adapter():
    t=make_tool('PythonTool',QualificationLevel.Q2_TESTED,'UTILITY');a=SubprocessToolAdapter(t);x=a.execute([sys.executable,'-c','print(2+3)'],timeout=5);assert x.returncode==0 and x.stdout.strip()=='5'

def test_subprocess_hash_outputs(tmp_path):
    p=tmp_path/'x.txt';p.write_text('abc');h=SubprocessToolAdapter.hash_outputs([p]);assert len(h[str(p)])==64

def test_dimensions_and_equation_check():
    assert (FORCE/(LENGTH**2)).compatible(PRESSURE)
    assert EquationDimensionalCheck('pressure',FORCE/(LENGTH**2),PRESSURE).enforce()

def test_problem_definition_and_graph():
    p=ProblemDefinition('P1','CFD',['dUdt+divF=0'],['U']);assert p.validate()
    g=EquationGraph();g.add_dependency('rho','momentum');g.add_dependency('momentum','energy');assert g.topological_order()==['rho','momentum','energy']

def test_equation_graph_missing_dependencies():
    g=EquationGraph();g.add_dependency('a','b');assert g.missing_dependencies({'a'})=={'b'}

def test_regime_detection():
    r=detect_cfd_regime(.1,1e4);assert 'incompressible' in r.labels and 'laminar' in r.labels
    r2=detect_cfd_regime(6,5e6,.2);assert 'hypersonic' in r2.labels and 'turbulent' in r2.labels and 'rarefied' in r2.labels
    s=detect_structural_regime(True,True,True,True);assert set(('dynamic','geometrically_nonlinear','materially_nonlinear','contact'))<=set(s.labels)

def test_solver_candidate_objective_and_pareto():
    a=SolverCandidate('a','CFD',True,.1,.4,.2,.1,.1,.1);b=SolverCandidate('b','CFD',True,.2,.2,.2,.1,.1,.1);c=SolverCandidate('c','CFD',True,.4,.5,.5,.5,.5,.5);front={x.name for x in pareto_front([a,b,c])};assert front=={'a','b'} and a.objective()>0

def test_routing_internal_low_risk():
    r=QualifiedToolRegistry();eng=SolverRoutingEngine(r);risk=assess_risk(RiskProfile());req=RouteRequest('CFD',risk,ScaleClass.S2_WORKSTATION);d=eng.route(req,[SolverCandidate('internal','CFD',True,verified_scale=ScaleClass.S3_MULTICORE_WORKSTATION)]);assert d.primary=='internal' and not d.external_mandatory

def test_routing_mandatory_external_with_qualified_tool():
    reg=QualifiedToolRegistry();reg.register(make_tool('QualifiedCFD',QualificationLevel.Q5_CERTIFICATION_ACCEPTABLE));risk=assess_risk(RiskProfile(triggers=frozenset({'airworthiness'})));req=RouteRequest('CFD',risk,ScaleClass.S2_WORKSTATION,certification_required=True);d=SolverRoutingEngine(reg).route(req,[SolverCandidate('internal','CFD',True,verified_scale=ScaleClass.S3_MULTICORE_WORKSTATION)]);assert d.external_mandatory and d.external_tool=='QualifiedCFD' and d.human_review

def test_routing_mandatory_missing_tool():
    risk=assess_risk(RiskProfile(triggers=frozenset({'human_safety'})));d=SolverRoutingEngine().route(RouteRequest('FEA',risk,ScaleClass.S2_WORKSTATION),[SolverCandidate('internal','FEA',True,verified_scale=ScaleClass.S3_MULTICORE_WORKSTATION)]);assert d.external_mandatory and d.external_tool is None and 'mandatory' in d.rationale[0]

@pytest.mark.parametrize('a,b,cls',[(1,1,'AGREEMENT'),(1,.995,'AGREEMENT'),(1,.98,'MINOR_DISCREPANCY'),(1,.9,'SIGNIFICANT_DISCREPANCY'),(1,.5,'CRITICAL_DISCREPANCY')])
def test_discrepancy_classes(a,b,cls): assert discrepancy(a,b).classification==cls

def test_richardson_gci_order():
    p=observed_order(.04,.01,2);assert abs(p-2)<1e-12
    ext=richardson_extrapolate(1.01,1.04,2,2);assert abs(ext-1.0)<1e-12
    assert grid_convergence_index(1.01,1.04,2,2)>0

def test_linear_residual():
    A=np.array([[3.,1.],[1.,2.]]);b=np.array([1.,0.]);x=np.linalg.solve(A,b);r=linear_residual(A,x,b);assert r['L2']<1e-14

def test_validation_metrics():
    m=validation_metrics([1,2,3],[1,2,3]);assert m['rmse']==0 and math.isclose(m['correlation'],1)

def test_confidence_engine():
    s,c=confidence_score(*([.95]*8));assert s>.9 and c==ConfidenceClass.C6_QUALIFIED_DEFINED_CONTEXT
    s2,c2=confidence_score(*([.5]*8));assert c2==ConfidenceClass.C2_VERIFIED

def test_lhs_and_transform():
    X=lhs_samples(20,[(-1,1),(10,20)],seed=4);assert X.shape==(20,2) and np.all((X[:,0]>=-1)&(X[:,0]<=1)) and np.all((X[:,1]>=10)&(X[:,1]<=20))

def test_local_sensitivity_methods():
    f=lambda x:x[0]**2+3*x[1]
    x=np.array([2.,4.]);assert np.allclose(local_sensitivity(f,x),[4,3],rtol=1e-5)
    assert np.allclose(local_sensitivity(f,x,method='forward'),[4,3],rtol=1e-5)

def test_complex_step_gradient():
    f=lambda x:x[0]**3+np.sin(x[1]);g=complex_step_gradient(f,[2.,.3]);assert np.allclose(g,[12,np.cos(.3)],rtol=1e-12)

def test_reliability_mc():
    out=reliability_monte_carlo(lambda x:x,lambda rng:rng.normal(),10000,seed=1);assert abs(out['probability_failure']-.5)<.03 and out['n']==10000

def test_robust_objective():
    assert robust_objective(None,[1,1,1],2)==1

def test_workflow_success_and_dependency():
    g=WorkflowGraph();g.add(WorkflowNode('a',lambda dependencies,context:2));g.add(WorkflowNode('b',lambda dependencies,context:dependencies['a']+3,('a',)));out=g.execute();assert out['status']=='PASS' and out['context']['b']==5

def test_workflow_retry():
    state={'n':0}
    def flaky(dependencies,context):
        state['n']+=1
        if state['n']==1:raise RuntimeError('once')
        return 7
    g=WorkflowGraph();g.add(WorkflowNode('x',flaky,retries=1));out=g.execute();assert out['status']=='PASS' and out['runs'][0].attempts==2

def test_factorial_sweep_and_experiment_plan():
    p=ExperimentPlan('h',{}, {},'solver',('m',),replications=2);assert p.validate();s=factorial_sweep({'a':[1,2],'b':['x','y']});assert len(s)==4

def test_provenance_graph(tmp_path):
    p=tmp_path/'a';q=tmp_path/'b';p.write_text('x');q.write_text('y');g=ProvenanceGraph();g.add_artifact(ArtifactRecord.from_file('raw','input',p));g.add_artifact(ArtifactRecord.from_file('result','output',q));g.add_edge('raw','result','solve');assert g.trace_to('result')=={'raw'} and g.to_dict()['edges'][0]['operation']=='solve'

def test_evidence_claim_pass():
    e=EvidenceEngine();
    for i,k in enumerate(('implementation','test','verification')):e.add_evidence(EvidenceRecord(f'E{i}',k,'PASS'))
    e.add_claim(ClaimRecord('C','verified',ClaimLevel.NUMERICALLY_VERIFIED,['E0','E1','E2']));c=e.evaluate('C');assert c.status=='PASS' and c.granted_level>=ClaimLevel.NUMERICALLY_VERIFIED

def test_evidence_claim_insufficient():
    e=EvidenceEngine();e.add_evidence(EvidenceRecord('E','implementation','PASS'));e.add_claim(ClaimRecord('C','validated',ClaimLevel.VALIDATED,['E']));assert e.evaluate('C').status=='INSUFFICIENT_EVIDENCE'

def test_qualification_ledger():
    q=QualificationLedger();q.set(CapabilityQualification('x',MaturityLevel.M4_BENCHMARKED,QualificationLevel.Q2_TESTED));assert q.require('x',MaturityLevel.M3_NUMERICALLY_VERIFIED,QualificationLevel.Q2_TESTED) and not q.require('x',qualification=QualificationLevel.Q4_INDUSTRIALLY_VALIDATED)

def test_governance_modes_and_review():
    assert enforce_mode(WorkflowMode.RESEARCH,True,False,False)
    risk=assess_risk(RiskProfile(criticality=.9,impact=.9,qualification_deficiency=.9));assert 'solver_review' in review_gates(risk,WorkflowMode.PRODUCTION)

def test_hpc_routing():
    r=route_hpc(1e4,1e9,256);assert r.backend=='CPU_SINGLE_NODE'
    r2=route_hpc(1e8,1e6,256,distributed_available=True);assert r2.distributed_required and r2.backend=='DISTRIBUTED_HPC'
    r3=route_hpc(1e8,1e6,256,distributed_available=False);assert r3.backend=='EXTERNAL_DISTRIBUTED_TOOL_REQUIRED'

def test_scaling_and_imbalance():
    s=strong_scaling({1:10,2:6,4:4});assert s[1]['speedup']>1
    w=weak_scaling({1:10,2:11,4:12});assert w[0]['efficiency']==1
    assert load_imbalance([10,10,20])>0

def test_domain_policies():
    low=assess_risk(RiskProfile());crit=assess_risk(RiskProfile(triggers=frozenset({'airworthiness'})))
    assert aircraft_structural_policy(crit,True).external_required
    assert cfd_policy(low,ScaleClass.S7_EXTREME_DISTRIBUTED).external_required
    assert sparse_policy(low,ScaleClass.S7_EXTREME_DISTRIBUTED).external_required
    assert cad_policy(low,industrial_interop=True).external_required
    assert gpu_training_policy(low,20,10).external_required

def test_multisolver_comparison():
    a=NormalizedResult('pressure','Pa',[1,2],'A');b=NormalizedResult('pressure','Pa',[1.001,2.001],'B');rows=compare_results([a,b]);assert rows[0]['classification']=='AGREEMENT'

def test_reproducibility_fingerprint_and_manifest(tmp_path):
    f=environment_fingerprint();assert len(f['fingerprint_sha256'])==64
    m=RunManifest('r','p','s','1','c','PASS');assert m.timestamp>0
    p=tmp_path/'x';p.write_text('data');ev=build_release_evidence([p]);assert len(ev['manifest_sha256'])==64 and ev['artifacts'][0]['bytes']==4

def test_model_validity_domain():
    d=ModelValidityDomain('m',{'Mach':ParameterRange(0,1)},unsupported_conditions=('rarefied',),required_input_quality=.8)
    assert d.assess({'Mach':.5},.9)['valid']
    bad=d.assess({'Mach':2},.5,('rarefied',));assert not bad['valid'] and len(bad['violations'])==3

def test_error_budget():
    e=ErrorBudget(discretization=3,iteration=4);assert e.rss()==5 and e.conservative_sum()==7 and e.dominant()[0]=='iteration' and abs(sum(e.fractions().values())-1)<1e-12

def test_polynomial_surrogate_exact_quadratic():
    x=np.linspace(-1,1,20)[:,None];y=2*x[:,0]**2+3*x[:,0]+1;m=fit_polynomial_surrogate(x,y,2);assert m.rmse<1e-12 and abs(m.predict([[.25]])-(2*.25**2+3*.25+1))<1e-10 and m.inside_domain([0])

def test_rbf_fit_and_predict():
    x=np.linspace(0,1,8)[:,None];y=np.sin(x[:,0]);m=fit_rbf(x,y,epsilon=2);pred=m.predict(x);assert np.max(np.abs(pred-y))<1e-6

def test_multifidelity_linear():
    low=np.array([1.,2.,3.]);high=2*low+1;m=multifidelity_linear(low,high);assert abs(m['rho']-2)<1e-12 and abs(m['delta']-1)<1e-12 and m['rmse']<1e-12

def test_active_selection():
    r=select_max_uncertainty([[0],[1],[2]],[.1,.9,.2]);assert r['index']==1 and r['point'][0]==1

def test_change_impact_plan():
    c=ChangeImpactAnalyzer();c.add_dependency('core','cfd');c.add_dependency('cfd','validation');c.add_test('cfd','test_cfd');c.add_test('validation','test_validation');c.add_qualification('validation','claim-cfd');p=c.plan(['core'],critical=True);assert p['affected_components']==['cfd','core','validation'] and p['tests']==['test_cfd','test_validation'] and p['full_qualification_required']

def test_qualification_change_detection():
    s=QualificationState('x',ClaimLevel.BENCHMARKED,'1','tool1','hw','regime');r=change_requires_requalification(s,code_version='2');assert r['required'] and r['reasons']==['code_version'];s.downgrade(ClaimLevel.TESTED,'changed');assert s.level==ClaimLevel.TESTED

def test_reporting_json():
    r=MachineReadableReport('p',.2,['internal'],'PASS','PASS',confidence=ConfidenceClass.C3_VALIDATED,evidence=['E']);d=json.loads(r.to_json());assert d['confidence']=='C3_VALIDATED' and executive_summary(r)['evidence_count']==1

def test_cosimulation_converges():
    # a = 0.5 b + 1; b = 0.25 a + 2 has stable fixed point
    out=fixed_point_cosim(lambda b:.5*b+1,lambda a:.25*a+2,[0.],[0.],tol=1e-10,max_iter=200,relaxation=.8);assert out.converged and out.residual_history[-1]<1e-10

def test_conservative_transfer():
    e=conservative_transfer_error([1,2],[1.5,1.5]);assert e['relative_error']==0

def test_precision_comparison():
    out=compare_precision(lambda x:x*x+1,[.1,.2,.3]);assert out['reference_dtype']=='float64' and out['metrics']['float64']['max_absolute']==0

def test_physics_numbers():
    assert math.isclose(reynolds(1.2,10,2,1.8e-5),1.2*10*2/1.8e-5)
    assert mach(340,340)==1
    assert prandtl(1000,1e-3,.6)>0
    assert peclet(2,3,.5)==12
    assert courant(10,.01,.2)==.5
    assert froude(10,5)>0 and knudsen(1e-7,.1)==1e-6
    assert biot(10,.1,2)==.5 and fourier(1e-5,100,.1)>0
    assert strouhal(2,.5,4)==.25 and grashof(9.81,3e-3,10,.5,1e-5)>0
    assert rayleigh(9.81,3e-3,10,.5,1e-5,1e-5)>0 and weber(1000,2,.1,.072)>0
    s=nondimensional_summary(rho=1.2,velocity=10,length=2,mu=1.8e-5,speed_of_sound=340);assert 'Re' in s and 'Ma' in s

def test_adjoint_gradient():
    A=np.array([[2.,0.],[0.,3.]]);j=np.array([1.,1.]);Rp=np.array([[1.,2.],[3.,4.]]);Jp=np.array([5.,6.]);o=adjoint_gradient(A,j,Rp,Jp);ref=Jp-np.linalg.solve(A.T,j)@Rp;assert np.allclose(o['gradient'],ref) and o['adjoint_residual']<1e-14

def test_pod_snapshots():
    t=np.linspace(0,1,20);X=np.vstack([np.sin(t),2*np.sin(t),np.cos(t)]);o=pod_snapshots(X,.99);assert 1<=o['rank']<=3 and o['captured_energy']>=.99

def test_dmd_linear_system():
    vals=[np.array([1.,1.])]
    A=np.diag([.9,.5])
    for _ in range(8):vals.append(A@vals[-1])
    X=np.column_stack(vals);o=dmd(X,2);ev=np.sort(np.abs(o['eigenvalues']));assert np.allclose(ev,[.5,.9],atol=1e-8)

def test_bayesian_grid_calibration():
    grid=np.linspace(-3,3,601);o=bayesian_grid_calibration(grid,lambda x:-.5*((x-1)/.5)**2);assert abs(o['mean']-1)<.02 and abs(o['map']-1)<.02 and o['ci95'][0]<1<o['ci95'][1]

def test_mahalanobis():
    assert abs(mahalanobis([1,0],np.eye(2))-1)<1e-12

def test_optimization_governance():
    f=lambda x:(x[0]-1)**2;out=verify_candidate([1],f,[lambda x:x[0]-2],[lambda x:x[0]-1]);assert out['feasible'] and out['objective']==0
    idx=pareto_nondominated([[1,3],[2,2],[3,1],[3,3]]);assert set(idx)=={0,1,2}
    pc=probabilistic_constraint([1,2,3,4],2.5,'le');assert pc['probability_satisfied']==.5

def test_benchmark_manager_and_rss():
    b=BenchmarkManager();r=b.run('add',lambda x:x+1,2,repeats=2);assert r['result']==3 and len(b.records)==1 and current_rss_bytes()>0

def test_endurance_manager_short():
    e=EnduranceManager(.01);r=e.run(.03,lambda i:{'invariant_ok':True});assert r['status']=='PASS' and r['iterations']>0
