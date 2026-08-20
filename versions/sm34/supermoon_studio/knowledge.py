from __future__ import annotations
import gzip
import hashlib
import json
import re
import sqlite3
import time
import zlib
from pathlib import Path
from typing import Iterable
from .config import settings

TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ_./:+-]{1,63}")
HEADING_RE = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\.\s+|=+\s*)?([A-Z][A-Z0-9 _./:+()&'\-]{7,})(?:\s*=+)?$")


def _index_terms(text: str, limit: int = 2200) -> str:
    # Intentionally excludes ID-heavy numeric and encoded/base64 payloads. Exact identifiers
    # still work through canonical stream fallback, while conceptual search stays compact.
    sample = text[:20000]
    if sample:
        whitespace = sum(1 for c in sample if c.isspace()) / len(sample)
        alnum = sum(1 for c in sample if c.isalnum()) / len(sample)
        if whitespace < 0.012 and alnum > 0.88:
            return "encoded payload artifact"
    terms = set()
    for m in TOKEN_RE.finditer(text):
        raw = m.group(0)
        token = raw.lower().strip("./:+-")
        if not (2 <= len(token) <= 40):
            continue
        # Random-looking mixed-case runs are common in inherited encoded blobs.
        if len(raw) >= 10 and raw.isalpha() and not (raw.islower() or raw.isupper()):
            continue
        terms.add(token)
        if len(terms) >= limit:
            break
    return " ".join(sorted(terms))


def _best_heading(lines: list[str], prior: str) -> str:
    best = prior
    for raw in lines:
        s = raw.strip().strip("=").strip()
        if not s or len(s) > 160:
            continue
        if re.match(r"^\d+(?:\.\d+)*\.\s+", s) or (s.upper() == s and any(c.isalpha() for c in s) and len(s) >= 8):
            best = s
    return best[:180]


class KnowledgeIndex:
    def __init__(self, db_path: Path | None = None, chunks_path: Path | None = None, source_gz: Path | None = None):
        self.db_path = Path(db_path or settings.knowledge_db)
        self.chunks_path = Path(chunks_path or settings.knowledge_chunks)
        self.source_gz = Path(source_gz or settings.knowledge_gz)

    @property
    def ready(self) -> bool:
        if not (self.db_path.exists() and self.chunks_path.exists() and self.source_gz.exists()):
            return False
        try:
            con = sqlite3.connect(self.db_path)
            try:
                meta = dict(con.execute("select key,value from meta").fetchall())
                chunks = int(con.execute("select count(*) from chunk_meta").fetchone()[0])
            finally:
                con.close()
            return (
                chunks > 0
                and meta.get("source_name") == self.source_gz.name
                and meta.get("source_gzip_bytes") == str(self.source_gz.stat().st_size)
                and meta.get("format") == "SM34_SEEKABLE_KNOWLEDGE_INDEX_V2"
            )
        except (OSError, sqlite3.Error, TypeError, ValueError):
            return False

    def stats(self) -> dict:
        base = {
            "ready": self.ready,
            "release": "SUPER MOON 34 NEW UNIVERSE",
            "source": str(self.source_gz),
            "source_name": self.source_gz.name,
            "source_exists": self.source_gz.exists(),
            "source_gzip_bytes": self.source_gz.stat().st_size if self.source_gz.exists() else 0,
        }
        if not self.ready:
            return base
        con = sqlite3.connect(self.db_path)
        try:
            rows = dict(con.execute("select key,value from meta").fetchall())
            count = con.execute("select count(*) from chunk_meta").fetchone()[0]
            base.update({"chunks": count, **rows, "db_bytes": self.db_path.stat().st_size, "chunk_store_bytes": self.chunks_path.stat().st_size})
        finally:
            con.close()
        return base

    def build(self, target_chars: int = 4 * 1024 * 1024, force: bool = False, progress=None) -> dict:
        if not self.source_gz.exists():
            raise FileNotFoundError(self.source_gz)
        if self.ready and not force:
            return self.stats()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_db = self.db_path.with_suffix(".building.sqlite3")
        tmp_chunks = self.chunks_path.with_suffix(".building.bin")
        for p in (tmp_db, tmp_chunks):
            if p.exists(): p.unlink()
        con = sqlite3.connect(tmp_db)
        con.execute("pragma journal_mode=OFF")
        con.execute("pragma synchronous=OFF")
        con.execute("pragma temp_store=MEMORY")
        con.execute("create table meta(key text primary key, value text not null)")
        con.execute("create table chunk_meta(chunk_id integer primary key, start_line integer, end_line integer, file_offset integer, compressed_bytes integer, raw_chars integer, heading text, sha256 text)")
        con.execute("create table chunk_terms(chunk_id integer primary key, heading text, terms text)")
        start = time.time(); line_no = 0; chunk_id = 0; offset = 0; prior_heading = "SUPER MOON 34 NEW UNIVERSE"
        buf: list[str] = []; chars = 0; start_line = 1
        sha_source = hashlib.sha256(); source_decompressed_bytes = 0

        with gzip.open(self.source_gz, "rb") as raw_source:
            for block in iter(lambda: raw_source.read(8 * 1024 * 1024), b""):
                sha_source.update(block)
                source_decompressed_bytes += len(block)

        def flush(fh, next_start_line: int | None = None):
            nonlocal chunk_id, offset, buf, chars, start_line, prior_heading
            if not buf:
                return
            text = "".join(buf)
            heading = _best_heading(buf, prior_heading)
            prior_heading = heading or prior_heading
            raw = text.encode("utf-8", errors="replace")
            comp = zlib.compress(raw, 1)
            fh.write(comp)
            digest = hashlib.sha256(raw).hexdigest()
            con.execute("insert into chunk_meta values(?,?,?,?,?,?,?,?)", (chunk_id, start_line, line_no, offset, len(comp), len(text), heading, digest))
            con.execute("insert into chunk_terms(chunk_id,heading,terms) values(?,?,?)", (chunk_id, heading, _index_terms(text)))
            offset += len(comp)
            chunk_id += 1
            buf = []
            chars = 0
            start_line = next_start_line if next_start_line is not None else line_no + 1
            if progress and chunk_id % 100 == 0:
                progress({"chunks": chunk_id, "line": line_no, "elapsed_s": round(time.time()-start, 2)})

        with gzip.open(self.source_gz, "rt", encoding="utf-8", errors="replace") as src, open(tmp_chunks, "wb") as data:
            for line_no, line in enumerate(src, 1):
                # Some inherited payloads contain extremely long single lines (e.g. encoded artifacts).
                # Split them into cache-sized pieces so indexing remains bounded in memory/time.
                pos = 0
                while pos < len(line):
                    room = max(1, target_chars - chars)
                    piece = line[pos:pos + room]
                    buf.append(piece); chars += len(piece); pos += len(piece)
                    if chars >= target_chars:
                        # If this flush occurs in the middle of one giant logical line,
                        # the next chunk still begins on that same source line.
                        flush(data, line_no if pos < len(line) else line_no + 1)
            flush(data, line_no + 1)
        meta = {
            "format": "SM34_SEEKABLE_KNOWLEDGE_INDEX_V2",
            "release": "SUPER MOON 34 NEW UNIVERSE",
            "source_name": self.source_gz.name,
            "source_gzip_bytes": str(self.source_gz.stat().st_size),
            "source_decompressed_sha256": sha_source.hexdigest(),
            "source_decompressed_bytes": str(source_decompressed_bytes),
            "total_lines": str(line_no),
            "total_chunks": str(chunk_id),
            "target_chunk_chars": str(target_chars),
            "built_unix": str(time.time()),
        }
        con.executemany("insert into meta(key,value) values(?,?)", meta.items()); con.commit(); con.close()
        if self.db_path.exists(): self.db_path.unlink()
        if self.chunks_path.exists(): self.chunks_path.unlink()
        tmp_db.replace(self.db_path); tmp_chunks.replace(self.chunks_path)
        return self.stats()

    def _read_chunk(self, con, chunk_id: int) -> tuple[dict, str]:
        row = con.execute("select chunk_id,start_line,end_line,file_offset,compressed_bytes,raw_chars,heading,sha256 from chunk_meta where chunk_id=?", (int(chunk_id),)).fetchone()
        if not row: raise KeyError(chunk_id)
        keys = ["chunk_id","start_line","end_line","file_offset","compressed_bytes","raw_chars","heading","sha256"]
        meta = dict(zip(keys,row))
        with open(self.chunks_path,"rb") as fh:
            fh.seek(meta["file_offset"]); comp = fh.read(meta["compressed_bytes"])
        text = zlib.decompress(comp).decode("utf-8", errors="replace")
        return meta, text

    @staticmethod
    def _excerpt(text: str, query_terms: list[str], radius: int = 700) -> str:
        lower = text.lower(); positions = [lower.find(t.lower()) for t in query_terms if t and lower.find(t.lower()) >= 0]
        pos = min(positions) if positions else 0
        a = max(0, pos-radius); b = min(len(text), pos+radius)
        return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")

    def authoritative_search(self, query: str, limit: int = 6) -> list[dict]:
        terms = [t.lower() for t in TOKEN_RE.findall(query or "") if len(t) >= 2][:8]
        if not terms or limit <= 0:
            return []
        sources = [
            (settings.supermoon_runtime_dir / "README_SM34_NEW_UNIVERSE.md", 6823794, "SM34 New Universe authoritative implementation", 7),
            (settings.supermoon_runtime_dir / "docs" / "SM34_ARCHITECTURE.md", 6823979, "SM34 New Universe architecture", 6),
            (settings.supermoon_runtime_dir / "docs" / "SM34_IMPLEMENTATION_REPORT.md", 6824071, "SM34 New Universe implementation report", 5),
            (settings.knowledge_dir / "SM32_QUALIFIED_RESEARCH_AUTHORITATIVE_SECTION.txt", 6807607, "SM32Q authoritative successor", 2),
            (settings.knowledge_dir / "SM32_FULL_IMPLEMENTATION_AUTHORITATIVE_SECTION.txt", 6785930, "SM32 full implementation successor", 1),
        ]
        hits = []
        for path, base_line, label, priority in sources:
            if not path.exists():
                continue
            lines = path.read_text("utf-8", errors="replace").splitlines()
            for i, line in enumerate(lines):
                low = line.lower()
                matched = sum(1 for t in terms if t in low)
                if not matched:
                    continue
                a=max(0,i-3); b=min(len(lines),i+4)
                excerpt="\n".join(lines[a:b]).strip()[:3200]
                hits.append({
                    "chunk_id": None, "start_line": base_line+i, "end_line": base_line+i,
                    "heading": label, "rank": float(-(matched + priority/10)),
                    "matched_terms": matched, "source": label, "excerpt": excerpt,
                    "_priority": priority,
                })
        hits.sort(key=lambda x:(-x["matched_terms"],-x["_priority"],-x["start_line"]))
        out=[];seen=set()
        for h in hits:
            key=(h["source"],h["start_line"]//20)
            if key in seen: continue
            seen.add(key);h.pop("_priority",None);out.append(h)
            if len(out)>=limit:break
        return out

    def search(self, query: str, limit: int = 8) -> list[dict]:
        q = (query or "").strip()
        if not q: return []
        terms = [t.lower() for t in TOKEN_RE.findall(q) if len(t) >= 2][:8]
        authoritative = self.authoritative_search(q, min(limit, 6))
        if not self.ready or not terms:
            streamed = self.stream_search(q, max(0, limit-len(authoritative)))
            return authoritative + streamed
        con = sqlite3.connect(self.db_path)
        try:
            # Only ~hundreds of coarse compressed chunks exist, so scoring the compact term
            # summaries in Python is faster and more robust than expanding a giant FTS index.
            rows = con.execute("select chunk_id, terms from chunk_terms").fetchall()
            candidates = []
            for chunk_id, term_blob in rows:
                tb = (term_blob or "").lower()
                matched = sum(1 for t in terms if t in tb)
                if matched:
                    candidates.append((matched, int(chunk_id)))
            candidates.sort(key=lambda x:(-x[0], -x[1]))
            out = []
            for indexed_match, chunk_id in candidates[:max(limit*6, 24)]:
                meta, text = self._read_chunk(con, chunk_id)
                low = text.lower()
                matched = sum(1 for t in terms if t in low)
                if matched == 0:
                    continue
                out.append({**meta, "rank": float(-matched), "matched_terms": matched, "excerpt": self._excerpt(text, terms)})
                if len(out) >= limit: break
            if out:
                merged = authoritative + out
                return merged[:limit]
        except sqlite3.OperationalError:
            pass
        finally:
            con.close()
        streamed = self.stream_search(q, max(0, limit-len(authoritative)))
        return (authoritative + streamed)[:limit]

    def stream_search(self, query: str, limit: int = 8) -> list[dict]:
        q = query.strip().lower()
        if not q or not self.source_gz.exists(): return []
        terms = [x for x in re.findall(r"\S+", q) if x][:6]
        out = []
        with gzip.open(self.source_gz, "rt", encoding="utf-8", errors="replace") as fh:
            for line_no, line in enumerate(fh, 1):
                low = line.lower()
                if all(t in low for t in terms):
                    out.append({"chunk_id": None, "start_line": line_no, "end_line": line_no, "heading": "stream match", "rank": 0.0, "excerpt": line.strip()[:1800]})
                    if len(out) >= limit: break
        return out

index = KnowledgeIndex()
