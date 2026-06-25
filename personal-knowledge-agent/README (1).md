# Personal Knowledge Base Agent

A Python CLI agent that lets you query your own notes using semantic search and AI-generated answers. Built with Groq (for chat) and HuggingFace (for embeddings).

---

## What It Does

1. Reads your notes from `.txt`, `.md`, `.pdf`, or `.docx` files
2. Splits them into chunks and converts each chunk into a vector (embedding)
3. Saves everything to `knowledge.json`
4. When you ask a question, finds the most semantically similar chunks
5. Passes those chunks to Groq to generate a grounded answer

---

## Project Structure

```
personal-knowledge-agent/
├── agent.py           # Main agent script
├── notes.txt          # Your plain text notes
├── research.md        # Markdown notes
├── productivity.pdf   # PDF notes
├── meeting_notes.docx # Word document notes
├── knowledge.json     # Auto-generated: chunks + embeddings
└── .env               # API keys (never commit this)
```

---

## Setup

### 1. Install Dependencies

```bash
pip install openai numpy requests python-dotenv pypdf python-docx
```

### 2. Create `.env` File

```env
GROQ_API_KEY=your_groq_api_key_here
HF_API_KEY=your_huggingface_token_here
```

- Get Groq key: https://console.groq.com
- Get HuggingFace token: https://huggingface.co/settings/tokens
  - Token type: Fine-grained
  - Permission: Make calls to Inference Providers ✅

### 3. Run

```bash
# Default — reads notes.txt
python agent.py

# Single file
python agent.py --file research.md
python agent.py --file report.pdf
python agent.py --file meeting_notes.docx

# Entire folder (all supported files)
python agent.py --folder .

# Force re-ingest after adding new files
python agent.py --folder . --reload
```

---

## Complete Flow (Block by Block)

### Block 1 — Client Setup

```python
_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
GROQ_MODEL = "openai/gpt-oss-120b"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
HF_API_KEY  = os.environ.get("HF_API_KEY")
```

Two separate APIs are used:
- **Groq** → for generating answers (chat completions)
- **HuggingFace** → for generating embeddings (vectors)

The OpenAI SDK works with Groq because Groq is OpenAI-compatible — just a different `base_url`.

---

### Block 2 — Ingestion (Reading Files)

```python
def read_txt(path)   # .txt and .md files
def read_pdf(path)   # .pdf via pypdf
def read_docx(path)  # .docx via python-docx
def load_file(path)  # routes to correct reader by extension
```

Each reader extracts raw text from the file. `load_file` acts as a router — it checks the file extension and calls the right reader automatically.

**Supported formats:**

| Extension | Reader |
|-----------|--------|
| `.txt` | Built-in open() |
| `.md` | Built-in open() |
| `.pdf` | pypdf |
| `.docx` | python-docx |

---

### Block 3 — Chunking

```python
def chunk_text(text, source, min_len=20):
```

Raw text is split into meaningful chunks. The logic:

1. Split by newlines into individual lines
2. Short lines (< 60 chars) are treated as **headings** — they become a prefix for the next chunk
3. Longer lines are appended to the current chunk
4. This groups headings with their content so queries like "what are the action items" can match

**Example — Before chunking:**
```
Action Items
Alice: Set up the embedding pipeline by Wednesday.
Bob: Integrate retrieval endpoint into frontend.
```

**After chunking:**
```
"Action Items: Alice: Set up the embedding pipeline by Wednesday. Bob: Integrate retrieval endpoint into frontend."
```

This is why semantic search works for heading-based questions.

---

### Block 4 — Embedding

```python
def embed_texts(texts):
    response = requests.post(
        f"https://router.huggingface.co/hf-inference/models/{EMBED_MODEL}/pipeline/feature-extraction",
        headers={"Authorization": f"Bearer {HF_API_KEY}"},
        json={"inputs": texts, "options": {"wait_for_model": True}}
    )
```

Each chunk is sent to HuggingFace's API which returns a **vector** — a list of 384 numbers representing the meaning of that chunk.

- Similar meanings → similar vectors
- This is what enables semantic search (not keyword matching)
- Model used: `BAAI/bge-small-en-v1.5` (lightweight, high quality)

---

### Block 5 — Storage

```python
def store_knowledge(chunks_with_sources, embeddings):
def load_knowledge():
```

All chunks + their vectors are saved to `knowledge.json`:

```json
[
  {
    "text": "RAG combines retrieval with generation...",
    "source": "notes.txt",
    "embedding": [0.021, -0.043, 0.198, ...],
    "created": "2025-06-25"
  }
]
```

On subsequent runs, `knowledge.json` is loaded directly — no re-embedding needed (saves API calls). Use `--reload` to force re-ingestion.

---

### Block 6 — Retrieval (Semantic Search)

```python
def cosine_similarity(a, b):
def retrieve(query, records, top_k=3):
```

When you ask a question:

1. Your question is embedded into a vector (same HuggingFace API)
2. Cosine similarity is calculated between your question vector and every stored chunk vector
3. Top 3 most similar chunks are returned

**Cosine similarity** measures the angle between two vectors:
- Score of `1.0` = identical meaning
- Score of `0.0` = completely unrelated
- Score of `-1.0` = opposite meaning

This is why "how do I avoid wasting time?" finds "time blocking" — same meaning, different words.

---

### Block 7 — Answer Generation

```python
def answer_query(query, top_results):
    prompt = f"""Answer the question using ONLY the notes below.
If the notes do not contain enough information, say so honestly.
Notes: {context_block}
Question: {query}"""
```

The top 3 retrieved chunks are passed to Groq with a strict prompt:
- "Answer using ONLY the notes below"
- If the answer isn't in the notes → it says so honestly (no hallucination)
- Temperature 0.2 → factual, consistent answers

---

### Block 8 — Main CLI Loop

```python
def main():
    # Parse --file / --folder / --reload flags
    # Ingest or load knowledge.json
    # Loop: ask question → retrieve → answer → repeat
```

The agent stays running in a loop so you can ask multiple questions in one session without re-loading the knowledge base each time.

---

## Full Data Flow Diagram

```
Your Files (.txt / .md / .pdf / .docx)
         │
         ▼
    load_file()          ← routes by extension
         │
         ▼
    chunk_text()         ← splits into paragraph chunks
                           headings merged with content
         │
         ▼
    embed_texts()        ← HuggingFace API
                           text → [0.02, -0.04, ...] (384 numbers)
         │
         ▼
    knowledge.json       ← stored on disk
         │
    ┌────┘
    │  (on query)
    ▼
embed_texts([query])     ← same HuggingFace API
         │
         ▼
cosine_similarity()      ← compare query vector vs all stored vectors
         │
         ▼
  top 3 chunks           ← most semantically similar
         │
         ▼
answer_query()           ← Groq API (gpt-oss-120b)
                           "answer ONLY from these notes"
         │
         ▼
    💬 Answer
```

---

## Configuration

| Constant | Default | Description |
|----------|---------|-------------|
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model for answer generation |
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Model for embeddings |
| `KNOWLEDGE_FILE` | `knowledge.json` | Where embeddings are cached |
| `top_k` | `3` | Number of chunks retrieved per query |
| `min_len` | `20` | Minimum chunk length (chars) |

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `model_not_found` on embeddings | Groq doesn't host embedding models | Use HuggingFace for embeddings (already fixed) |
| `ConnectionError` on HuggingFace | `api-inference.huggingface.co` blocked | Use `router.huggingface.co` URL (already fixed) |
| `Invalid username or password` | HF token missing Inference permission | Enable "Make calls to Inference Providers" on token |
| Wrong file retrieved | `knowledge.json` is stale | Run with `--reload` flag |
| Meeting questions not answered | Headings not embedded | Fixed by heading-aware chunking |
| `No content found` | No supported files in folder | Check files are `.txt` `.md` `.pdf` or `.docx` |

---

## Dependencies

```
openai          — Groq API client (OpenAI-compatible)
numpy           — Cosine similarity calculation
requests        — HuggingFace API calls
python-dotenv   — Load .env file
pypdf           — Read PDF files
python-docx     — Read Word documents
```
