from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Any, Sequence
import subprocess, hashlib, os, platform, shlex
from .enums import QualificationLevel
from ..core import InvalidInput, BackendUnavailable

@dataclass(frozen=True)
class QualifiedTool:
    tool_name: str
    vendor_or_project: str
    version: str='unknown'
    domains: tuple[str,...]=()
    solver_types: tuple[str,...]=()
    supported_equations: tuple[str,...]=()
    verified_use_cases: tuple[str,...]=()
    certification_contexts: tuple[str,...]=()
    supported_hardware: tuple[str,...]=()
    validated_scale_range: tuple[int,int] | None=None
    input_formats: tuple[str,...]=()
    output_formats: tuple[str,...]=()
    automation_interface: str=''
    license: str='unknown'
    qualification_level: QualificationLevel=QualificationLevel.Q0_UNKNOWN
    validation_evidence: tuple[str,...]=()
    benchmark_evidence: tuple[str,...]=()
    known_limitations: tuple[str,...]=()
    known_failure_modes: tuple[str,...]=()
    reproducibility_notes: str=''
    executable: str | None=None
    def supports_domain(self,domain:str)->bool:return domain.lower() in {d.lower() for d in self.domains}

class QualifiedToolRegistry:
    def __init__(self): self._tools: dict[str,QualifiedTool]={}
    def register(self,tool: QualifiedTool, replace: bool=False):
        if not tool.tool_name.strip(): raise InvalidInput('tool_name required')
        key=tool.tool_name.lower()
        if key in self._tools and not replace: raise InvalidInput(f'duplicate tool: {tool.tool_name}')
        self._tools[key]=tool; return tool
    def get(self,name:str)->QualifiedTool:return self._tools[name.lower()]
    def list(self)->list[QualifiedTool]:return sorted(self._tools.values(),key=lambda x:x.tool_name.lower())
    def candidates(self,domain:str,minimum:QualificationLevel=QualificationLevel.Q0_UNKNOWN)->list[QualifiedTool]:
        return [t for t in self.list() if t.supports_domain(domain) and t.qualification_level>=minimum]
    def best(self,domain:str,minimum:QualificationLevel=QualificationLevel.Q0_UNKNOWN)->QualifiedTool | None:
        c=self.candidates(domain,minimum)
        return max(c,key=lambda t:(int(t.qualification_level),len(t.validation_evidence),len(t.benchmark_evidence))) if c else None
    def as_dict(self):return {t.tool_name:asdict(t) for t in self.list()}

@dataclass
class ToolExecution:
    tool_name: str; command: list[str]; returncode: int; stdout: str; stderr: str; elapsed_s: float; environment: dict[str,str]; output_hashes: dict[str,str]=field(default_factory=dict)

class SubprocessToolAdapter:
    """Generic auditable CLI adapter. It confers no qualification on the wrapped tool."""
    def __init__(self, tool: QualifiedTool): self.tool=tool
    def validate_input(self,command:Sequence[str]):
        if not command: raise InvalidInput('empty tool command')
        exe=command[0]
        if self.tool.executable and os.path.basename(exe)!=os.path.basename(self.tool.executable): raise InvalidInput('command executable does not match tool record')
        return True
    def execute(self, command:Sequence[str], cwd:str|Path|None=None, timeout:float|None=None, env:dict[str,str]|None=None)->ToolExecution:
        import time
        self.validate_input(command); merged=os.environ.copy(); merged.update(env or {})
        t=time.perf_counter()
        try:p=subprocess.run(list(command),cwd=cwd,env=merged,text=True,capture_output=True,timeout=timeout,check=False)
        except FileNotFoundError as e: raise BackendUnavailable(str(e)) from e
        return ToolExecution(self.tool.tool_name,list(command),p.returncode,p.stdout,p.stderr,time.perf_counter()-t,{'platform':platform.platform(),'python':platform.python_version()})
    @staticmethod
    def hash_outputs(paths:Iterable[str|Path])->dict[str,str]:
        out={}
        for p in paths:
            p=Path(p); out[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        return out
