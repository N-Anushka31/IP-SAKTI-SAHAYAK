
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from pathlib import Path
import sqlite3, json, csv, io, re
from datetime import datetime
from rag import retrieve

BASE = Path(__file__).resolve().parent
DB = BASE.parent / "database" / "ipsakti.db"
DB.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="IP-SAKTI SAHAYAK API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS innovations(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      brand TEXT,
      description TEXT,
      ingredients TEXT,
      traditional_knowledge TEXT,
      intended_use TEXT,
      target_population TEXT,
      dosage_form TEXT,
      novel_aspect TEXT,
      category TEXT DEFAULT 'Proprietary Ayurvedic Medicine',
      risk TEXT DEFAULT 'Low Risk',
      status TEXT DEFAULT 'Completed',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS actions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      innovation_id INTEGER,
      title TEXT NOT NULL,
      owner TEXT DEFAULT 'Inventor',
      due_date TEXT,
      status TEXT DEFAULT 'To Do'
    );
    CREATE TABLE IF NOT EXISTS evidence(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      innovation_id INTEGER,
      title TEXT NOT NULL,
      type TEXT,
      status TEXT DEFAULT 'Pending Review',
      source TEXT,
      added_on TEXT
    );
    CREATE TABLE IF NOT EXISTS reports(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      innovation_id INTEGER,
      name TEXT NOT NULL,
      type TEXT NOT NULL,
      generated_on TEXT NOT NULL,
      generated_by TEXT DEFAULT 'Ananya Verma',
      status TEXT DEFAULT 'Completed'
    );
    CREATE TABLE IF NOT EXISTS searches(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      innovation_id INTEGER,
      keywords TEXT,
      ip_type TEXT,
      results_json TEXT,
      searched_on TEXT NOT NULL
    );
    """)
    count = c.execute("SELECT COUNT(*) FROM innovations").fetchone()[0]
    if count == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        seed = [
            ("INV-2025-00124","HerboRelief Pain Relief Oil","HerboRelief",
             "An Ayurvedic topical herbal oil intended for muscle and joint comfort using botanical extracts.",
             "Mahanarayan oil, Eucalyptus, Wintergreen, Sesame","Yes","Muscle pain relief","Adults","Oil",
             "Specific combination and proportion of standardized botanical extracts","Proprietary Ayurvedic Medicine","Moderate","Completed"),
            ("INV-2025-00125","Ashwagandha Stress Relief Tablets","AshvaCalm Tablets",
             "An Ayurvedic tablet formulation containing Ashwagandha, Brahmi and Jatamansi for stress and cognitive support.",
             "Ashwagandha 400 mg, Brahmi 200 mg, Jatamansi 100 mg","Yes","Stress relief, anxiety management, cognitive support","Adults (18 years and above)","Tablet",
             "Combination of standardized extracts in a specific ratio","Proprietary Ayurvedic Medicine","Low Risk","Completed"),
            ("INV-2025-00126","Guduchi Immuno Support Syrup","Guduchi Plus",
             "A botanical syrup formulation based on Guduchi extract for general wellness support.","Guduchi extract, honey base","Yes","General wellness","Adults","Syrup",
             "Standardized extraction and formulation process","Classical Medicine","Low Risk","Completed"),
            ("INV-2025-00127","Kumkumadi Radiance Cream","Kumkumadi Radiance",
             "A cosmetic herbal cream inspired by traditional Kumkumadi preparations.","Saffron, sandalwood, sesame oil","Yes","Skin wellness","Adults","Cream",
             "Modern stable cream base with traditional botanicals","Cosmetic","Moderate","Under Review"),
            ("INV-2025-00128","Brahmi Memory Support Capsule","Brahmi Focus",
             "A capsule using Bacopa monnieri extract for cognitive wellness.","Bacopa monnieri extract","Yes","Cognitive wellness","Adults","Capsule",
             "Standardized extract concentration","Proprietary Ayurvedic Medicine","Low Risk","Completed"),
            ("INV-2025-00129","Triphala Digestive Churna","Triphala Balance",
             "A classical powdered botanical formulation for digestive wellness.","Amalaki, Bibhitaki, Haritaki","Yes","Digestive wellness","Adults","Churna",
             "Classical formulation","Classical Medicine","Low Risk","Completed")
        ]
        for s in seed:
            cur=c.execute("""INSERT INTO innovations
              (code,name,brand,description,ingredients,traditional_knowledge,intended_use,
               target_population,dosage_form,novel_aspect,category,risk,status,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (*s, now, now))
        first = c.execute("SELECT id FROM innovations WHERE code='INV-2025-00124'").fetchone()[0]
        acts = [
            ("Refine claim set to improve novelty","Ananya Verma","2025-05-20","In Progress"),
            ("Conduct detailed prior art search","IP Expert","2025-05-18","In Progress"),
            ("Complete ABS documentation","Ananya Verma","2025-05-22","Overdue"),
            ("Obtain expert opinion on patentability","IP Expert","2025-05-25","To Do"),
            ("Prepare regulatory dossier for EU","Regulatory Advisor","2025-05-30","To Do")
        ]
        c.executemany("INSERT INTO actions(innovation_id,title,owner,due_date,status) VALUES(?,?,?,?,?)",
                      [(first,*a) for a in acts])
        evs = [
            ("Mahanarayan Taila – Composition Study","Traditional Knowledge","Verified","AYUSH Database","2025-05-08"),
            ("Eucalyptus globulus – Anti-inflammatory Data","Scientific Literature","Verified","PubMed","2025-05-07"),
            ("US20220123456A1","Patent Document","Pending Review","USPTO","2025-05-06"),
            ("ABS Form – Part A","ABS Document","Pending Review","NBA Portal","2025-05-05"),
            ("HerboRelief Oil – Formulation Details","Internal Document","Verified","User Upload","2025-05-04")
        ]
        c.executemany("INSERT INTO evidence(innovation_id,title,type,status,source,added_on) VALUES(?,?,?,?,?,?)",
                      [(first,*e) for e in evs])
    c.commit(); c.close()

init_db()

class InnovationIn(BaseModel):
    name: str
    brand: str = ""
    description: str = ""
    ingredients: str = ""
    traditional_knowledge: str = "Yes"
    intended_use: str = ""
    target_population: str = "Adults"
    dosage_form: str = "Tablet"
    novel_aspect: str = ""

class SearchIn(BaseModel):
    keywords: str
    ip_type: str = "Patent"
    innovation_id: int | None = None

class ActionIn(BaseModel):
    innovation_id: int
    title: str
    owner: str = "Inventor"
    due_date: str = ""
    status: str = "To Do"

def rowdict(r): return dict(r) if r else None

@app.get("/api/health")
def health():
    return {"ok": True, "service": "IP-SAKTI SAHAYAK"}

@app.get("/api/innovations")
def innovations():
    c=conn()
    rows=c.execute("SELECT * FROM innovations ORDER BY updated_at DESC, id DESC").fetchall()
    c.close()
    return [rowdict(r) for r in rows]

@app.get("/api/innovations/{iid}")
def innovation(iid:int):
    c=conn(); r=c.execute("SELECT * FROM innovations WHERE id=?",(iid,)).fetchone(); c.close()
    if not r: raise HTTPException(404,"Innovation not found")
    return rowdict(r)

@app.post("/api/innovations")
def create_innovation(x: InnovationIn):
    c=conn()
    now=datetime.now().strftime("%Y-%m-%d %H:%M")
    n=c.execute("SELECT COUNT(*) FROM innovations").fetchone()[0]+1
    code=f"INV-{datetime.now().year}-{n:05d}"
    # Simple transparent rules-based classification for a prototype.
    txt=(x.description+" "+x.ingredients+" "+x.intended_use).lower()
    category="Cosmetic" if any(k in txt for k in ["cream","lotion","cosmetic","skin"]) else "Proprietary Ayurvedic Medicine"
    risk="Moderate" if any(k in txt for k in ["pain","clinical","high dose","novel"]) else "Low Risk"
    status="Completed"
    cur=c.execute("""INSERT INTO innovations
      (code,name,brand,description,ingredients,traditional_knowledge,intended_use,target_population,
       dosage_form,novel_aspect,category,risk,status,created_at,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (code,x.name,x.brand,x.description,x.ingredients,x.traditional_knowledge,x.intended_use,
       x.target_population,x.dosage_form,x.novel_aspect,category,risk,status,now,now))
    iid=cur.lastrowid
    c.execute("INSERT INTO actions(innovation_id,title,owner,due_date,status) VALUES(?,?,?,?,?)",
              (iid,"Review AI classification and IP pathway","Inventor","", "To Do"))
    c.commit(); r=c.execute("SELECT * FROM innovations WHERE id=?",(iid,)).fetchone(); c.close()
    return rowdict(r)

@app.put("/api/innovations/{iid}")
def update_innovation(iid:int, x: InnovationIn):
    c=conn(); now=datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute("""UPDATE innovations SET name=?,brand=?,description=?,ingredients=?,traditional_knowledge=?,
      intended_use=?,target_population=?,dosage_form=?,novel_aspect=?,updated_at=? WHERE id=?""",
      (x.name,x.brand,x.description,x.ingredients,x.traditional_knowledge,x.intended_use,
       x.target_population,x.dosage_form,x.novel_aspect,now,iid))
    c.commit(); r=c.execute("SELECT * FROM innovations WHERE id=?",(iid,)).fetchone(); c.close()
    if not r: raise HTTPException(404,"Innovation not found")
    return rowdict(r)

@app.get("/api/dashboard")
def dashboard():
    c=conn()
    total=c.execute("SELECT COUNT(*) FROM innovations").fetchone()[0]
    pending=c.execute("SELECT COUNT(*) FROM actions WHERE status!='Completed'").fetchone()[0]
    evidence=c.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    high=c.execute("SELECT COUNT(*) FROM innovations WHERE risk='Moderate'").fetchone()[0]
    opp=max(1,total + 6)
    alerts=max(1, min(9, high+2))
    recent=c.execute("SELECT * FROM innovations ORDER BY updated_at DESC,id DESC LIMIT 5").fetchall()
    acts=c.execute("SELECT * FROM actions WHERE status!='Completed' ORDER BY id DESC LIMIT 5").fetchall()
    c.close()
    return {"total_innovations":total,"ip_opportunities":opp,"pending_actions":pending,
            "alerts":alerts,"evidence_items":evidence,"moderate_risks":high,
            "recent_innovations":[rowdict(r) for r in recent],
            "pending":[rowdict(r) for r in acts]}

@app.get("/api/risk")
def risk():
    c=conn()
    total=c.execute("SELECT COUNT(*) FROM innovations").fetchone()[0]
    ev=c.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    verified=c.execute("SELECT COUNT(*) FROM evidence WHERE status='Verified'").fetchone()[0]
    actions=c.execute("SELECT COUNT(*) FROM actions WHERE status!='Completed'").fetchone()[0]
    overdue=c.execute("SELECT COUNT(*) FROM actions WHERE status='Overdue'").fetchone()[0]
    c.close()
    score=58 if total else 0
    return {"overall":"Moderate","score":score,"risk_areas":[
        {"name":"Patentability","level":"High","score":72,"trend":"up"},
        {"name":"Prior Art Conflicts","level":"Medium","score":55,"trend":"up"},
        {"name":"TK & Biodiversity","level":"Medium","score":48,"trend":"flat"},
        {"name":"Regulatory Compliance","level":"Medium","score":52,"trend":"up"},
        {"name":"ABS Compliance","level":"Low","score":30,"trend":"down"}],
        "total_risk_areas":12,"open_actions":actions,"overdue":overdue,
        "evidence_items":ev,"verified":verified,"pending_review":max(0,ev-verified),
        "mitigation_progress":65}

@app.get("/api/actions")
def actions():
    c=conn(); rows=c.execute("SELECT * FROM actions ORDER BY id DESC").fetchall(); c.close()
    return [rowdict(r) for r in rows]

@app.post("/api/actions")
def add_action(x:ActionIn):
    c=conn(); cur=c.execute("INSERT INTO actions(innovation_id,title,owner,due_date,status) VALUES(?,?,?,?,?)",
                         (x.innovation_id,x.title,x.owner,x.due_date,x.status))
    c.commit(); r=c.execute("SELECT * FROM actions WHERE id=?",(cur.lastrowid,)).fetchone(); c.close()
    return rowdict(r)

@app.patch("/api/actions/{aid}")
def update_action(aid:int, status:str="Completed"):
    c=conn(); c.execute("UPDATE actions SET status=? WHERE id=?",(status,aid)); c.commit()
    r=c.execute("SELECT * FROM actions WHERE id=?",(aid,)).fetchone(); c.close()
    return rowdict(r)

@app.get("/api/evidence")
def evidence():
    c=conn(); rows=c.execute("SELECT * FROM evidence ORDER BY id DESC").fetchall(); c.close()
    return [rowdict(r) for r in rows]

@app.post("/api/prior-art/search")
def prior_art(x:SearchIn):
    terms=[t.strip().lower() for t in re.split(r"[,;\s]+",x.keywords) if t.strip()]
    base=[
      {"publication":"WO 2021/123456 A1","title":"Ashwagandha root extract composition for stress and anxiety management","applicant":"Natural Remedies Pvt. Ltd.","date":"18 Mar 2021","similarity":82,"relevance":"High"},
      {"publication":"IN 2020/1045678 A","title":"Herbal composition comprising Withania somnifera for stress relief","applicant":"AyurGen Labs","date":"22 Dec 2020","similarity":68,"relevance":"High"},
      {"publication":"US 2019/0345678 A1","title":"Adaptogenic herbal blend for cognitive support","applicant":"Herbalife LLC","date":"14 Nov 2019","similarity":54,"relevance":"Medium"},
      {"publication":"EP 3214567 A1","title":"Combination of Bacopa and Withania for improving memory","applicant":"Phytomed AG","date":"09 Jul 2017","similarity":42,"relevance":"Medium"},
      {"publication":"IN 2017/012345 A","title":"Tablet containing Brahmi and Jatamansi extracts","applicant":"Ayurveda Care","date":"19 Apr 2017","similarity":28,"relevance":"Low"}
    ]
    # lightweight keyword matching to make results respond to input
    for r in base:
        overlap=sum(1 for t in terms if t in (r["title"]+" "+r["applicant"]).lower())
        r["similarity"]=min(95,max(18,r["similarity"]+overlap*3))
    if x.innovation_id:
        c=conn()
        c.execute("INSERT INTO searches(innovation_id,keywords,ip_type,results_json,searched_on) VALUES(?,?,?,?,?)",
                  (x.innovation_id,x.keywords,x.ip_type,json.dumps(base),datetime.now().strftime("%Y-%m-%d %H:%M")))
        c.commit(); c.close()
    return {"matches":len(base),"results":base,"summary":{"high":sum(r["similarity"]>=75 for r in base),
      "medium":sum(50<=r["similarity"]<75 for r in base),
      "low":sum(25<=r["similarity"]<50 for r in base),
      "very_low":sum(r["similarity"]<25 for r in base)}}

@app.get("/api/search-history")
def search_history():
    c=conn(); rows=c.execute("SELECT * FROM searches ORDER BY id DESC LIMIT 20").fetchall(); c.close()
    return [rowdict(r) for r in rows]

@app.get("/api/tk")
def tk():
    return {
      "match_found":"Yes","similarity":62,"level":"Moderate","pointer_count":3,"resources":4,
      "aspects":[
        ["Use of Mahanarayan Oil for muscle pain","Similar"],
        ["Use of Wintergreen for analgesic effect","Similar"],
        ["Use of Eucalyptus for anti-inflammatory use","Similar"],
        ["Specific combination & proportion","Low Similarity"]
      ],
      "pointers":[
        ["TKDL-IN-12345","Mahanarayan Taila for muscle pain relief","High"],
        ["TKDL-IN-67890","Eucalyptus leaves oil for anti-inflammatory","Medium"],
        ["TKDL-IN-54321","Gaultheria fragrantissima (Wintergreen) uses","Medium"]
      ],
      "resources":[
        ["Eucalyptus globulus","Leaves Oil","Plant"],
        ["Gaultheria fragrantissima","(Wintergreen) Leaf Oil","Plant"],
        ["Sesamum indicum","(Sesame) Seed Oil","Plant"],
        ["Ricinus communis","(Castor) Seed Oil","Plant"]
      ],
      "abs":{"applicable":"Applicable","reason":"Innovation uses biological resources subject to the Biological Diversity Act, 2002.",
            "requirements":["Prior Informed Consent (PIC)","Mutually Agreed Terms (MAT)","Benefit Sharing","National Biodiversity Authority (NBA) Approval"]}
    }

@app.get("/api/regulatory")
def regulatory():
    return {
      "pathway":"Ayurvedic Proprietary Medicine","authority":"Ministry of AYUSH, Govt. of India",
      "guidelines":"AYUSH GCP Guidelines, 2022","license":"Yes – Manufacturing & Sale License",
      "safety":"Required as per applicable standards","documentation":"Product Dossier, GMP Certificate",
      "status":"Compliant",
      "requirements":[["Product classification","Done"],["Ingredient approval check","Compliant"],
        ["Safety assessment","Done"],["Good Manufacturing Practice (GMP)","Required"],
        ["Stability studies","Required"],["Labelling compliance","Required"],["Adverse event monitoring plan","Recommended"]],
      "countries":[["India","Ayurvedic Proprietary Medicine","6 – 12 months","GMP, Safety, Quality","Strong","High"],
        ["USA","Botanical Drug (IND/NDA)","2 – 3 years","Clinical Trials, FDA Approval","Strong","Medium"],
        ["European Union","Traditional Herbal Medicinal Product","1 – 2 years","THMPD Compliance","Strong","Medium"],
        ["Australia","Listed Medicine (TGA)","1 – 2 years","TGA Evidence Requirements","Strong","High"],
        ["UAE","Herbal / Traditional Medicine","6 – 12 months","Product Dossier","Moderate","Medium"]]
    }

@app.get("/api/ai")
def ai():
    return {"welcome":"I’m your IP-SAKTI AI Assistant. I can help with patentability, prior art, TK & biodiversity, regulations, and more."}

@app.post("/api/ai/chat")
def ai_chat(payload:dict):
    q=str(payload.get("message",""))
    retrieved=retrieve(q, top_k=3)
    text=q.lower()
    if "patent" in text or "patentable" in text:
        answer="Patentability should be assessed against novelty, inventive step, industrial applicability and applicable statutory exclusions. The retrieved guidance below is the evidence used for this preliminary response. A detailed prior-art search and claim review by an IP professional is recommended."
    elif "prior art" in text or "similar" in text:
        answer="Prior-art assessment should compare the formulation, ingredients, process, use and claim features against earlier disclosures. Review the retrieved sources and then use the IP & Prior-Art module for a broader search."
    elif "regulation" in text or "ayush" in text or "license" in text:
        answer="For an Ayurvedic product in India, first establish the applicable product category and regulatory pathway, then verify licensing, quality, safety, manufacturing and labelling requirements against current official guidance."
    elif "tk" in text or "traditional knowledge" in text or "biodiversity" in text or "abs" in text:
        answer="Where biological resources or associated traditional knowledge are involved, screen for traditional-knowledge prior art and assess applicable access and benefit-sharing obligations before proceeding."
    else:
        answer="I can help assess patentability, prior art, traditional knowledge, biodiversity/ABS and regulatory pathways. I retrieved the most relevant stored sources for this question below."
    return {"answer":answer,"time":datetime.now().strftime("%I:%M %p"),"confidence":retrieved[0]["score"] if retrieved else 0,"citations":[{"title":x["title"],"source":x["source"],"snippet":x["snippet"]} for x in retrieved]}

@app.get("/api/reports")
def reports():
    c=conn(); rows=c.execute("SELECT * FROM reports ORDER BY id DESC").fetchall(); c.close()
    return [rowdict(r) for r in rows]

@app.post("/api/reports/generate")
def generate_report(payload:dict):
    iid=payload.get("innovation_id") or 1
    typ=payload.get("type","Patentability Report")
    names={"IP Landscape Report":"IP Landscape","Prior Art Search Report":"Prior Art Search",
           "Patentability Report":"Patentability","Regulatory Compliance Report":"Regulatory Compliance",
           "TK & Biodiversity Report":"TK & Biodiversity"}
    c=conn(); inv=c.execute("SELECT * FROM innovations WHERE id=?",(iid,)).fetchone()
    if not inv: iid=1; inv=c.execute("SELECT * FROM innovations WHERE id=1").fetchone()
    now=datetime.now().strftime("%Y-%m-%d %H:%M")
    name=f"{typ} - {inv['name']}"
    cur=c.execute("INSERT INTO reports(innovation_id,name,type,generated_on) VALUES(?,?,?,?)",(iid,name,typ,now))
    report_id=cur.lastrowid
    c.commit(); c.close()
    return {"id":report_id,"innovation_id":iid,"name":name,"type":typ,"generated_on":now,"generated_by":"IP-SAKTI User","status":"Completed"}

@app.get("/api/reports/download/{rid}")
def download_report(rid:int):
    c=conn(); r=c.execute("""SELECT reports.*, innovations.name AS innovation_name, innovations.code
                             FROM reports JOIN innovations ON innovations.id=reports.innovation_id
                             WHERE reports.id=?""",(rid,)).fetchone(); c.close()
    if not r: raise HTTPException(404,"Report not found")
    content=f"""IP-SAKTI SAHAYAK REPORT
Report: {r['name']}
Innovation: {r['innovation_name']} ({r['code']})
Type: {r['type']}
Generated: {r['generated_on']}
Status: {r['status']}

This prototype report is decision-support information based on stored application data.
It is not legal advice.
"""
    return StreamingResponse(io.BytesIO(content.encode()),media_type="text/plain",
                             headers={"Content-Disposition":f"attachment; filename=report-{rid}.txt"})

@app.get("/api/export/dashboard.csv")
def export_csv():
    data=dashboard()
    out=io.StringIO(); w=csv.writer(out)
    w.writerow(["Metric","Value"])
    for k,v in data.items():
        if isinstance(v,(int,float,str)): w.writerow([k,v])
    return StreamingResponse(io.BytesIO(out.getvalue().encode()),media_type="text/csv",
                             headers={"Content-Disposition":"attachment; filename=ipsakti-dashboard.csv"})

@app.get("/", response_class=HTMLResponse)
def root():
    frontend = BASE.parent / "frontend" / "index.html"
    return FileResponse(frontend)

# Serve frontend assets from the same FastAPI process, so only one command is needed.
# Frontend is not needed for Streamlit deployment
