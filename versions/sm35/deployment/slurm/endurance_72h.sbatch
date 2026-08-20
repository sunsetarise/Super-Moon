#!/bin/bash
#SBATCH --job-name=sm35-endurance72
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=73:00:00
#SBATCH --requeue
#SBATCH --signal=B:USR1@300
set -euo pipefail
python3 tools/run_endurance_72h.py --output evidence/SM35_ENDURANCE_72H/telemetry.jsonl --checkpoint evidence/SM35_ENDURANCE_72H/checkpoint.json
