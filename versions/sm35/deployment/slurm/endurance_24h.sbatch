#!/bin/bash
#SBATCH --job-name=sm35-endurance24
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=25:00:00
#SBATCH --requeue
set -euo pipefail
python3 tools/run_endurance_24h.py --output evidence/SM35_ENDURANCE_24H/telemetry.jsonl --checkpoint evidence/SM35_ENDURANCE_24H/checkpoint.json
