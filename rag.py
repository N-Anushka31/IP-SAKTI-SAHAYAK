"""Small, transparent local RAG engine for the IP-SAKTI prototype.
It retrieves relevant chunks from the bundled source corpus and returns
source titles, snippets and a normalized confidence score. No external API key is required.
"""
from pathlib import Path
import re

DOCS = Path(__file__).resolve().parent / "documents"

def _tokens(text):
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))

def _load():
    records=[]
    for p in sorted(DOCS.glob("*.txt")):
        raw=p.read_text(encoding="utf-8")
        parts=re.split(r"\n(?=## )", raw)
        for part in parts:
            lines=part.strip().splitlines()
            if not lines: continue
            title=lines[0].replace("## ","").strip()
            body=" ".join(lines[1:]).strip()
            records.append({"title":title or p.stem,"source":p.stem.replace("_"," ").title(),"text":body})
    return records

RECORDS=_load()

def retrieve(query, top_k=3):
    q=_tokens(query)
    scored=[]
    for r in RECORDS:
        t=_tokens(r["text"]+" "+r["title"])
        overlap=len(q & t)
        score=min(99, round(45 + overlap/max(1,len(q))*55)) if overlap else 0
        if overlap:
            scored.append((score,r))
    scored.sort(key=lambda x:x[0], reverse=True)
    out=[]
    for score,r in scored[:top_k]:
        snippet=r["text"][:300].rstrip()+("…" if len(r["text"])>300 else "")
        out.append({"title":r["title"],"source":r["source"],"snippet":snippet,"score":score})
    return out
