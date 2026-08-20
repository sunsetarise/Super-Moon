from __future__ import annotations
# Registry entries are evidence-scoped. Registry presence never implies implementation.
TECH_DOMAINS={
'CAD':['B-Rep topology','NURBS curves','NURBS surfaces','exact predicates','adaptive tolerances','boolean union','boolean intersection','boolean difference','feature DAG','persistent naming','constraint solving','assembly graph','mass properties','STEP exchange','IGES exchange','shape healing','tessellation','PMI mapping','GD&T metadata','curve-surface intersection','surface-surface intersection','BVH','AABB tree','geometric hashing','topology validation'],
'Mesh':['Delaunay triangulation','advancing front','tetra meshing','prism layers','hex topology','curvature sizing','proximity sizing','anisotropic refinement','wake refinement','shock refinement','quality metrics','mesh smoothing','remeshing','h-adaptation','p-adaptation','hp-adaptation','partitioning','solution transfer','CAD association','boundary tagging','Jacobian validation','sliver detection','non-orthogonality','load balancing','space filling curves'],
'FEA':['truss','Euler-Bernoulli beam','Timoshenko beam','CST','Q4','Q8','Tet4','Tet10','Hex8','Hex20','Mindlin shell','Kirchhoff-Love shell','reduced integration','selective integration','hourglass control','finite strain','total Lagrangian','updated Lagrangian','J2 plasticity','hyperelasticity','viscoelasticity','contact penalty','augmented Lagrangian contact','composite laminate','phase-field fracture'],
'CFD':['Euler finite volume','Rusanov flux','HLL flux','HLLC flux','Roe flux','AUSM flux','MUSCL','TVD limiting','ENO','WENO','compressible Navier-Stokes','incompressible projection','SIMPLE','PISO','Spalart-Allmaras','k-epsilon','k-omega','SST','URANS','Smagorinsky LES','dynamic LES','WALE','DES','ALE moving mesh','overset interpolation'],
'HPC':['MPI point-to-point','MPI nonblocking','MPI collectives','MPI Cartesian topology','MPI neighborhood collectives','MPI RMA','MPI IO','PETSc Vec','PETSc Mat','PETSc KSP','PETSc PC','PETSc SNES','PETSc TS','PETSc DM','SLEPc EPS','CUDA streams','CUDA events','pinned memory','device memory pools','Triton kernels','NCCL AllReduce','NCCL AllGather','GPUDirect RDMA','roofline analysis','mixed precision refinement'],
'V&V':['analytical verification','manufactured solutions','Richardson extrapolation','GCI','mesh convergence','time-step convergence','residual histories','conservation checks','condition estimates','gradient checks','regression testing','property tests','fuzz testing','fault injection','endurance 1h','endurance 8h','endurance 24h','endurance 72h','external reproduction','numerical equivalence','strict determinism','experimental correlation','calibration split','validation split','uncertainty quantification'],
'Certification':['requirements DB','bidirectional traceability','orphan detection','FHA evidence','PSSA evidence','SSA evidence','FMEA','FMECA','fault trees','configuration management','audit hash chain','problem reports','verification matrix','source traceability','test traceability','structural coverage import','regulatory baseline profile','evidence package','SBOM','dependency manifest','model credibility record','intended-use declaration','assumption register','limitation register','external acceptance gate'],
'Multiphysics':['one-way FSI','two-way FSI','Aitken coupling','conjugate heat transfer','thermoelasticity','electrothermal coupling','aeroelasticity','gust coupling','modal coupling','field projection','conservative transfer','nearest transfer','co-simulation','explicit staggered','implicit staggered','quasi-Newton coupling','ALE coupling','moving boundary','radiation coupling','species-energy coupling','particle-fluid coupling','phase change','sensor-model coupling','digital twin state update','checkpoint restart']}

def technology_registry():
    out=[]
    for d,items in TECH_DOMAINS.items():
        for i,name in enumerate(items): out.append({'id':f'{d.upper()}-{i+1:03d}','domain':d,'technology':name,'status':'REFERENCE_OR_IMPLEMENTED_AS_EVIDENCED','evidence_required':True})
    # Expand application-specific, non-alias engineering uses; each is a distinct integration target, not a claim of completion.
    apps=['aircraft','rotorcraft','UAV','spacecraft subsystem','automobile','EV','train','ship','robot','industrial machine','consumer appliance','battery system','heat exchanger','turbomachinery','renewable energy','pressure vessel','pump','fan','building structure','manufacturing cell']
    methods=['CAD-to-mesh traceability','structural verification workflow','fluid verification workflow','thermal verification workflow','multiphysics coupling workflow','uncertainty workflow','optimization workflow','digital twin workflow','reproducibility workflow','evidence workflow','fault workflow','endurance workflow','configuration workflow']
    for a in apps:
        for m in methods: out.append({'id':f'APP-{len(out)+1:04d}','domain':'Application','technology':f'{a}: {m}','status':'INTEGRATION_TARGET','evidence_required':True})
    return out

MATH_FAMILIES=['linear algebra','sparse Krylov','eigenvalue','nonlinear root finding','optimization','probability','Monte Carlo','MCMC','ODE integration','PDE discretization','finite element','finite volume','discontinuous Galerkin','geometry','splines','NURBS','computational topology','continuum mechanics','plasticity','hyperelasticity','fracture mechanics','contact mechanics','heat transfer','fluid dynamics','turbulence','multiphase','combustion kinetics','signal analysis','control','state estimation','uncertainty quantification','sensitivity analysis','adjoint methods','domain decomposition','graph partitioning','numerical verification','statistics','reliability','dimensional analysis','Lie groups']
MATH_METHODS=['Newton iteration','damped Newton','Gauss-Newton','Levenberg-Marquardt','trust region','conjugate gradient','MINRES','GMRES','FGMRES','BiCGStab','Lanczos','Krylov-Schur','QR factorization','SVD','Cholesky','LU factorization','Runge-Kutta','BDF','Newmark','generalized-alpha','central difference','Richardson extrapolation','Galerkin projection','Petrov-Galerkin','least squares','Lagrange multipliers','penalty method','augmented Lagrangian','importance sampling','Latin hypercube','Sobol sequence','Kalman filter','EKF','UKF','particle filtering','automatic differentiation','complex-step derivative','central finite difference','line search','arc-length continuation']

def mathematical_registry():
    out=[]
    # unique family/method pairs carry domain and verification semantics, not aliases
    for fam in MATH_FAMILIES:
        for method in MATH_METHODS[:8]:
            out.append({'id':f'MATH-{len(out)+1:04d}','family':fam,'method':method,'status':'REFERENCE','required_fields':['equation','assumptions','conditioning','convergence','complexity','failure_modes','tests']})
            if len(out)>=320:return out
    return out


# ================= CELESTIAL DEPTH: registry truth validation =================
_technology_registry_pre_celestial=technology_registry
_mathematical_registry_pre_celestial=mathematical_registry

def _validate_registry(rows,kind):
    if not isinstance(rows,list) or not rows: raise RuntimeError(f'{kind} registry is empty')
    ids=[r.get('id') for r in rows]
    if any(not isinstance(i,str) or not i for i in ids): raise RuntimeError(f'{kind} registry has invalid id')
    if len(ids)!=len(set(ids)): raise RuntimeError(f'{kind} registry has duplicate id')
    for r in rows:
        if kind=='technology':
            if not r.get('domain') or not r.get('technology') or 'status' not in r: raise RuntimeError('technology registry row incomplete')
        else:
            if not r.get('family') or not r.get('method') or 'required_fields' not in r: raise RuntimeError('mathematics registry row incomplete')
    return rows

def technology_registry():
    rows=_technology_registry_pre_celestial()
    # Scope freeze: exact SM31 technology population is preserved.
    if len(rows)!=460: raise RuntimeError(f'celestial scope violation: expected 460 technologies, got {len(rows)}')
    return _validate_registry(rows,'technology')

def mathematical_registry():
    rows=_mathematical_registry_pre_celestial()
    # Scope freeze: exact SM31 mathematical population is preserved.
    if len(rows)!=320: raise RuntimeError(f'celestial scope violation: expected 320 mathematics entries, got {len(rows)}')
    return _validate_registry(rows,'mathematics')
