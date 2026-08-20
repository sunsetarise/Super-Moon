#!/bin/bash
#SBATCH --job-name=sm36-petsc
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --time=02:00:00
#SBATCH --output=sm36-petsc-%j.out
#SBATCH --error=sm36-petsc-%j.err
set -euo pipefail
: "${SM35_TREE:?Set SM35_TREE to the reconstructed inherited SM35 tree}"
for ranks in 1 2 3 4 8; do
  nodes=1
  if [ "$ranks" -ge 4 ]; then nodes=2; fi
  srun --kill-on-bad-exit=1 --nodes="$nodes" --ntasks="$ranks" \
    python3 "$SM35_TREE/tools/petsc_poisson_worker.py"
done
sacct -j "$SLURM_JOB_ID" --format=JobID,State,ExitCode,Elapsed,AllocNodes,AllocTRES,MaxRSS -P
