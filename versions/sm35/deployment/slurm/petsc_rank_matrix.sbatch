#!/bin/bash
#SBATCH --job-name=sm35-petsc
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --time=02:00:00
#SBATCH --output=sm35-petsc-%j.out
#SBATCH --error=sm35-petsc-%j.err
set -euo pipefail
for ranks in 1 2 3 4 8; do
  srun --kill-on-bad-exit=1 --nodes=$([ "$ranks" -ge 4 ] && echo 2 || echo 1) --ntasks="$ranks" python3 tools/petsc_poisson_worker.py
done
sacct -j "$SLURM_JOB_ID" --format=JobID,State,ExitCode,Elapsed,AllocNodes,AllocTRES,MaxRSS -P
