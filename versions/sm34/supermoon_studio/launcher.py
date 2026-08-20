from __future__ import annotations
import json
import threading
import time
import urllib.request
import webbrowser
from .config import settings
from .main import run


def browser_probe():
    for _ in range(120):
        state=settings.runtime_dir/"server-state.json"
        if state.exists():
            try:
                url=json.loads(state.read_text("utf-8"))["url"]
                with urllib.request.urlopen(url+"api/health",timeout=1.0) as r:
                    if r.status==200:
                        webbrowser.open(url,new=2); return
            except Exception: pass
        time.sleep(.25)

if __name__=="__main__":
    threading.Thread(target=browser_probe,daemon=True).start()
    run()
