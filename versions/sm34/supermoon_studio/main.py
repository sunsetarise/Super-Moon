from __future__ import annotations
import json
import os
import platform
import socket
import sys
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from . import APP_NAME, __version__
from .config import settings
from .analysis_engine import analyzer
from .knowledge import index
from .report_engine import build_scientific_pdf, build_patent_pdf, output_name
from .schemas import AnalyzeRequest, SearchRequest, ReportRequest
from .sm32_bridge import runtime_status as sm32_runtime_status
from .sm34_bridge import overview as sm34_overview, runtime_status as sm34_runtime_status, validation as sm34_validation

app=FastAPI(title=APP_NAME,version=__version__)
app.mount("/static",StaticFiles(directory=settings.static_dir),name="static")

STARTED=time.time()

@app.get("/")
def root(): return FileResponse(settings.static_dir/"index.html")

@app.get("/api/health")
def health():
    babylon=(settings.static_dir/"vendor"/f"babylon-{settings.babylon_version}.js")
    return {
        "ok": True,
        "app": APP_NAME,
        "version": __version__,
        "uptime_s": round(time.time()-STARTED,2),
        "python": sys.version.split()[0],
        "python_runtime": {
            "executable": sys.executable,
            "base_executable": getattr(sys, "_base_executable", sys.executable),
            "implementation": sys.implementation.name,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
        },
        "platform": platform.platform(),
        "knowledge": index.stats(),
        "sm34_runtime": sm34_runtime_status(),
        "sm32_runtime": sm32_runtime_status(),
        "babylon": {"version":settings.babylon_version,"local_bundle":babylon.exists(),"path":str(babylon)},
        "output_dir": str(settings.output_dir),
    }

@app.get("/api/sm34/overview")
def new_universe_overview():
    try:
        return sm34_overview(include_validation=False)
    except Exception as e:
        raise HTTPException(500,f"{type(e).__name__}: {e}")

@app.get("/api/sm34/validation")
def new_universe_validation():
    try:
        return {"ok": True, "validation": sm34_validation()}
    except Exception as e:
        raise HTTPException(500,f"{type(e).__name__}: {e}")

@app.post("/api/analyze")
def analyze(req:AnalyzeRequest):
    try: return analyzer.analyze(req.prompt,req.knowledge_limit)
    except Exception as e: raise HTTPException(400,f"{type(e).__name__}: {e}")

@app.post("/api/knowledge/search")
def search(req:SearchRequest):
    try: return {"query":req.query,"results":index.search(req.query,req.limit),"stats":index.stats()}
    except Exception as e: raise HTTPException(500,f"{type(e).__name__}: {e}")

@app.post("/api/upload/prompt")
async def upload_prompt(file:UploadFile=File(...)):
    name=(file.filename or "prompt.txt").lower()
    if not any(name.endswith(x) for x in (".txt",".md",".json",".yaml",".yml",".prompt")):
        raise HTTPException(415,"Use a text-based prompt file (.txt, .md, .json, .yaml).")
    data=await file.read()
    if len(data)>10_000_000: raise HTTPException(413,"Prompt file exceeds 10 MB upload limit.")
    text=data.decode("utf-8",errors="replace")
    return {"filename":file.filename,"characters":len(text),"prompt":text}

@app.post("/api/report/scientific")
def scientific(req:ReportRequest):
    try:
        analysis=req.analysis or analyzer.analyze(req.prompt,8)
        path=build_scientific_pdf(req.prompt,analysis,output_name("scientific",analysis))
        return {"ok":True,"filename":path.name,"download_url":f"/api/output/{path.name}"}
    except Exception as e: raise HTTPException(500,f"{type(e).__name__}: {e}")

@app.post("/api/report/patent")
def patent(req:ReportRequest):
    try:
        analysis=req.analysis or analyzer.analyze(req.prompt,8)
        path=build_patent_pdf(req.prompt,analysis,output_name("patent",analysis))
        return {"ok":True,"filename":path.name,"download_url":f"/api/output/{path.name}"}
    except Exception as e: raise HTTPException(500,f"{type(e).__name__}: {e}")

@app.get("/api/output/{filename}")
def output(filename:str):
    safe=Path(filename).name
    p=settings.output_dir/safe
    if not p.exists() or p.suffix.lower()!=".pdf": raise HTTPException(404,"PDF not found")
    return FileResponse(p,media_type="application/pdf",filename=p.name)

@app.get("/api/output")
def outputs():
    rows=[]
    for p in sorted(settings.output_dir.glob("*.pdf"),key=lambda x:x.stat().st_mtime,reverse=True)[:100]:
        rows.append({"filename":p.name,"bytes":p.stat().st_size,"modified":p.stat().st_mtime,"download_url":f"/api/output/{p.name}"})
    return {"items":rows}


def choose_port(host:str,preferred:int)->int:
    for port in range(preferred,preferred+30):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            try:s.bind((host,port));return port
            except OSError:continue
    raise RuntimeError("No free local port found")


def run():
    import uvicorn
    port=choose_port(settings.host,settings.port)
    state={"host":settings.host,"port":port,"url":f"http://{settings.host}:{port}/","pid":os.getpid(),"started":time.time()}
    (settings.runtime_dir/"server-state.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
    print(f"\n{APP_NAME} {__version__}\nURL: {state['url']}\nRuntime log/state: {settings.runtime_dir}\n")
    uvicorn.run(app,host=settings.host,port=port,log_level="info")

if __name__=="__main__": run()
