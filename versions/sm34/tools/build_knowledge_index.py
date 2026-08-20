from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from supermoon_studio.knowledge import index

if __name__=="__main__":
    print("Building full seekable Super Moon 34 New Universe knowledge cache from canonical TXT.GZ...")
    def progress(x): print(f"  chunks={x['chunks']} line={x['line']} elapsed={x['elapsed_s']}s",flush=True)
    stats=index.build(force="--force" in sys.argv,progress=progress)
    print("Knowledge index ready:")
    for k,v in stats.items(): print(f"  {k}: {v}")
