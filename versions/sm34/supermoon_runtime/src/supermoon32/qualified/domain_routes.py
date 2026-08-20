from __future__ import annotations
from dataclasses import dataclass
from .risk import RiskAssessment
from .enums import ScaleClass,RiskClass

@dataclass(frozen=True)
class DomainRoutePolicy:
    domain:str; external_required:bool; independent_verification:bool; requirements:tuple[str,...]; internal_role:tuple[str,...]

def aircraft_structural_policy(risk:RiskAssessment,certification_required=True):
    ext=certification_required or risk.risk_class in (RiskClass.VERY_HIGH,RiskClass.CRITICAL)
    return DomainRoutePolicy('AIRCRAFT_STRUCTURES',ext,True,('mesh_convergence','validated_material_data','load_case_traceability','uncertainty_bounds','human_review') if ext else ('mesh_convergence',),('model_generation','load_case_organization','independent_fea_verification','optimization','uq','evidence_aggregation'))

def cfd_policy(risk:RiskAssessment,scale:ScaleClass,billion_cell=False):
    ext=billion_cell or scale>=ScaleClass.S6_LARGE_DISTRIBUTED or risk.risk_class in (RiskClass.VERY_HIGH,RiskClass.CRITICAL)
    return DomainRoutePolicy('CFD',ext,ext or risk.required_independent_verification,('grid_convergence','conservation','physics_sensitivity','convergence_monitoring'),('reduced_verification_cases','mesh_studies','post_processing','uq','discrepancy_analysis'))

def sparse_policy(risk:RiskAssessment,scale:ScaleClass):
    ext=scale>=ScaleClass.S6_LARGE_DISTRIBUTED or risk.risk_class is RiskClass.CRITICAL
    return DomainRoutePolicy('SPARSE_LINEAR_ALGEBRA',ext,ext or risk.required_independent_verification,('residual_recompute','conditioning_assessment','memory_estimate','preconditioner_selection'),('subproblem_verification','residual_verification','condition_analysis'))

def cad_policy(risk:RiskAssessment,industrial_interop=False):
    ext=industrial_interop or risk.risk_class is RiskClass.CRITICAL
    return DomainRoutePolicy('CAD_GEOMETRY',ext,ext,('topology_validation','tolerance_analysis','degenerate_entity_scan','roundtrip_comparison'),('geometry_audit','topology_verification','repair_proposal','comparison'))

def gpu_training_policy(risk:RiskAssessment,model_bytes:float,device_bytes:float,multi_gpu=False):
    ext=model_bytes>device_bytes or risk.risk_class in (RiskClass.VERY_HIGH,RiskClass.CRITICAL)
    req=('memory_estimate','gradient_monitoring','checkpointing','reproducibility','throughput_monitoring')
    return DomainRoutePolicy('GPU_TRAINING',ext,True if ext else risk.required_independent_verification,req,('experiment_orchestration','verification','checkpoint_validation','metrics_analysis'))
