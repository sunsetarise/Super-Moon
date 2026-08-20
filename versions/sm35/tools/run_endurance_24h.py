#!/usr/bin/env python3
import argparse
from pathlib import Path
from endurance_common import run

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--checkpoint", type=Path, required=True)
args = parser.parse_args()
raise SystemExit(run(24, args.output, args.checkpoint))
