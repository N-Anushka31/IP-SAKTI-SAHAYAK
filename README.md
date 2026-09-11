# IP-SAKTI SAHAYAK

A simple local prototype for multilingual IP, traditional-knowledge, biodiversity/ABS and regulatory decision support for Ayurveda. It includes a transparent local RAG layer using the bundled source notes.

## Folder structure

```text
IP-SAKTI-SAHAYAK
├── backend
│   ├── main.py
│   ├── rag.py
│   ├── requirements.txt
│   └── documents
└── frontend
    ├── index.html
    ├── style.css
    └── app.js
└── database
    └── (SQLite database is created automatically)
```

No BAT files are required.

## Run locally

1. Install Python 3.10+ if needed.
2. Open this project folder in VS Code.
3. Open one terminal and run:

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

4. Open **http://127.0.0.1:8000** in your browser.

The FastAPI server serves the frontend, API, SQLite database and local RAG in one process, so a second terminal is not needed.

## RAG

The AI Assistant retrieves relevant chunks from `backend/documents/` and returns source names, snippets and a confidence score. This is a local demonstration RAG pipeline and does not require an API key. For production, replace the bundled notes with a curated, versioned authoritative corpus and connect an approved embedding/vector store and LLM.

## Important

This is a prototype for demonstration and decision support. It is not legal advice, and the bundled source notes are not a substitute for current official statutes, rules, databases or professional review.
