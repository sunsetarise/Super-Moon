"""SUPER MOON 31.0 OMEGA Industrial Engineering Dominion.
Additive successor layer for SM30.1. No certification claim is made by this package.
"""
__version__='31.0.0'
RELEASE='SUPER MOON 31.0 OMEGA INDUSTRIAL ENGINEERING DOMINION'
from .core import CapabilityLevel,Status,Provenance,Quantity,UNIT


# ================= CELESTIAL DEPTH PROFILE (depth-only, scope-frozen) =================
# This marker does not add a product domain or algorithm. It identifies the hardened
# implementation profile applied to the existing SUPER MOON 31.0 capability surface.
DEPTH_PROFILE='CELESTIAL_DEPTH'
DEPTH_CONTRACT='SM31_EXISTING_CAPABILITY_ONLY'
