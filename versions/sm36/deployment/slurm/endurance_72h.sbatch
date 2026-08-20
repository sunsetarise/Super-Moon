#!/bin/bash
#SBATCH --job-name=sm36-endurance72
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --time=73:00:00
#SBATCH --output=sm36-endurance72-%j.out
#SBATCH --error=sm36-endurance72-%j.err
set -euo pipefail
: "${SM35_TREE:?Set SM35_TREE to the reconstructed inherited SM35 tree}"
srun --kill-on-bad-exit=1 python3 "$SM35_TREE/tools/run_endurance_72h.py" "$@"
sacct -j "$SLURM_JOB_ID" --format=JobID,State,ExitCode,Elapsed,AllocNodes,AllocTRES,MaxRSS -P
