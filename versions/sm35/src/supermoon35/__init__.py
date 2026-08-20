"""Additive qualification layer for SUPER MOON 34 New Universe."""

from .contracts import ClaimLevel, ExecutionStatus, PhysicalReceipt, ValidationError
from .qualification import ReleaseDecision, score_release

VERSION = "35.0.0"
RELEASE_NAME = "SUPER MOON 35 NEW UNIVERSE QUALIFICATION CANDIDATE"
RELEASE_STATE = "BLOCKED_PENDING_REAL_EXECUTION"

__all__ = [
    "ClaimLevel",
    "ExecutionStatus",
    "PhysicalReceipt",
    "RELEASE_NAME",
    "RELEASE_STATE",
    "ReleaseDecision",
    "VERSION",
    "ValidationError",
    "score_release",
]
