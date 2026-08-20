#!/bin/bash
# Site must add approved account, partition, modules/container, and workload command.
#SBATCH --job-name=sm34-endurance
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=72:30:00
#SBATCH --output=sm34-endurance-%j.out
#SBATCH --error=sm34-endurance-%j.err
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1
python3 -m supermoon34 qualification

