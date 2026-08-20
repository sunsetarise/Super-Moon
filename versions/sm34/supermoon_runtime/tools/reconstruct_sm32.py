#!/usr/bin/env python3
"""Reconstruct SUPER MOON 31 QP1 + SUPER MOON 32 payloads from merged TXT.GZ.

The parser uses the declared byte count, not line splitting, so files without a
terminal newline reconstruct exactly. Later occurrences overwrite earlier ones,
which implements the merged artifact's authoritative-successor overlay policy.
"""
from __future__ import annotations
import argparse,gzip,hashlib,re
from pathlib import Path
HDRS=[
    re.compile(rb'^<<<SM31_CELESTIAL_QP1_FILE path="([^"]+)" sha256="([0-9a-f]{64})" bytes="(\d+)">>>\r?\n$'),
    re.compile(rb'^<<<SM32_FILE path="([^"]+)" sha256="([0-9a-f]{64})" bytes="(\d+)">>>\r?\n$'),
]
ENDS={b'<<<END_SM31_CELESTIAL_QP1_FILE>>>',b'<<<END_SM32_FILE>>>'}

def reconstruct(merged,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
    with gzip.open(merged,'rb') as f:
        while True:
            line=f.readline()
            if not line:break
            match=None
            for rx in HDRS:
                m=rx.match(line)
                if m:match=m;break
            if not match:continue
            path=match.group(1).decode('utf-8');sha=match.group(2).decode();n=int(match.group(3));data=f.read(n)
            if len(data)!=n:raise EOFError(f'truncated payload: {path}')
            # Historical payloads may end the byte-counted content with a newline
            # and place the end marker immediately after it. New payloads may use
            # one explicit separator newline when the file itself lacks one.
            sep=f.read(1)
            if sep==b'<':
                end=(sep+f.readline()).strip()
            else:
                if sep not in (b'\n',b'\r'):
                    raise ValueError(f'missing payload separator after {path}')
                if sep==b'\r':
                    lf=f.read(1)
                    if lf!=b'\n':raise ValueError(f'invalid CR separator after {path}')
                end=f.readline().strip()
            if end not in ENDS:raise ValueError(f'invalid end marker after {path}: {end!r}')
            actual=hashlib.sha256(data).hexdigest();ok=actual==sha
            dest=out/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            rows.append({'path':path,'bytes':n,'sha256':sha,'verified':ok})
            if not ok:raise ValueError(f'SHA-256 mismatch: {path}')
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('merged');ap.add_argument('out');args=ap.parse_args();rows=reconstruct(args.merged,args.out);print(f'extracted={len(rows)} verified={sum(r["verified"] for r in rows)}')
if __name__=='__main__':main()
