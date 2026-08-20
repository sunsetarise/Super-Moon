#!/bin/bash
# Site must add approved account, partition, modules/container, and absolute release path.
#SBATCH --job-name=sm34-petsc
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --time=01:00:00
#SBATCH --output=sm34-petsc-%j.out
#SBATCH --error=sm34-petsc-%j.err
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1
srun --kill-on-bad-exit=1 python3 -m supermoon34 qualification

