from __future__ import annotations
from dataclasses import dataclass
from .core import InvalidInput
_SCALE={'m':1.,'mm':1e-3,'cm':1e-2,'km':1e3,'Pa':1.,'kPa':1e3,'MPa':1e6,'GPa':1e9,'kg':1.,'g':1e-3,'s':1.,'ms':1e-3,'rad':1.,'deg':0.017453292519943295}
_DIM={'m':'L','mm':'L','cm':'L','km':'L','Pa':'P','kPa':'P','MPa':'P','GPa':'P','kg':'M','g':'M','s':'T','ms':'T','rad':'A','deg':'A'}
@dataclass(frozen=True)
class Quantity:
    value:float;unit:str
    def to(self,unit):
        if self.unit not in _SCALE or unit not in _SCALE or _DIM[self.unit]!=_DIM[unit]:raise InvalidInput('incompatible or unknown unit')
        return Quantity(self.value*_SCALE[self.unit]/_SCALE[unit],unit)
