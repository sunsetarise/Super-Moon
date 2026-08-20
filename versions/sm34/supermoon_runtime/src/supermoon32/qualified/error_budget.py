from __future__ import annotations
from dataclasses import dataclass,asdict
import math
from ..core import InvalidInput

@dataclass(frozen=True)
class ErrorBudget:
    discretization:float=0.0; iteration:float=0.0; model:float=0.0; parameter:float=0.0; measurement:float=0.0; roundoff:float=0.0; surrogate:float=0.0; data:float=0.0
    def __post_init__(self):
        if any(v<0 for v in asdict(self).values()):raise InvalidInput('error components must be non-negative')
    def conservative_sum(self):return float(sum(asdict(self).values()))
    def rss(self):return math.sqrt(sum(v*v for v in asdict(self).values()))
    def dominant(self):return max(asdict(self).items(),key=lambda kv:kv[1])
    def fractions(self):
        s=self.conservative_sum();return {k:(v/s if s else 0.0) for k,v in asdict(self).items()}
