"""
Personal Knowledge Base Agent (Extended)
Supports: .txt, .md, .pdf, .docx files or entire folders
Usage:
    python agent.py                        # reads notes.txt by default
    python agent.py --file report.pdf      # single file
    python agent.py --folder ./my-notes    # entire folder
"""

import json
import os
import argparse
import numpy as np
import requests
from openai import OpenAI
from datetime import date
from dotenv import load_dotenv
load_dotenv()

_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

GROQ_MODEL = "openai/gpt-oss-120b"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
HF_API_KEY  = os.environ.get("HF_API_KEY")
KNOWLEDGE_FILE = "knowledge.json"



# ──────────────────────────────────────────────
# 1. INGESTION — supports .txt, .md, .pdf, .docx
# ──────────────────────────────────────────────

def read_txt(path):
    """Read plain text or markdown files."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_pdf(path):
    """Extract text from PDF files (requires: pip install pypdf)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("Install pypdf to read PDFs:  pip install pypdf")
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_docx(path):
    """Extract text from Word documents (requires: pip install python-docx)."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("Install python-docx to read Word files:  pip install python-docx")
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def load_file(path):
    """Route a file to the correct reader based on its extension."""
    ext = os.path.splitext(path)[1].lower()
    readers = {
        ".txt":  read_txt,
        ".md":   read_txt,
        ".pdf":  read_pdf,
        ".docx": read_docx,
    }
    if ext not in readers:
        print(f"  ⚠  Skipping unsupported file: {path}")
        return None
    print(f"  ✓  Reading {os.path.basename(path)}")
    return readers[ext](path)

def chunk_text(text, source, min_len=20):
    lines = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""

    for line in lines:
        # if line is short (likely a heading), start a new grouped chunk
        if len(line) < 60:
            if current:
                chunks.append((current.strip(), source))
            current = line + ": "  # attach heading as prefix
        else:
            current += line + " "

    if current.strip():
        chunks.append((current.strip(), source))

    return chunks


def ingest(file_path=None, folder_path=None):
    """
    Ingest one file or all supported files in a folder.
    Returns list of (chunk_text, source) tuples.
    """
    all_chunks = []

    if folder_path:
        files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if os.path.splitext(f)[1].lower() in (".txt", ".md", ".pdf", ".docx")
        ]
        if not files:
            print(f"No supported files found in '{folder_path}'")
            return []
        for fp in sorted(files):
            text = load_file(fp)
            if text:
                all_chunks.extend(chunk_text(text, os.path.basename(fp)))

    elif file_path:
        text = load_file(file_path)
        if text:
            all_chunks.extend(chunk_text(text, os.path.basename(file_path)))

    else:
        # Default: notes.txt in current directory
        all_chunks.extend(chunk_text(read_txt("notes.txt"), "notes.txt"))

    return all_chunks


# ──────────────────────────────────────────────
# 2. EMBEDDING — HuggingFace Inference API
# ──────────────────────────────────────────────
def embed_texts(texts):
    """Embed texts via HuggingFace Inference API (no local model needed)."""
    response = requests.post(
        f"https://router.huggingface.co/hf-inference/models/{EMBED_MODEL}/pipeline/feature-extraction",
        headers={"Authorization": f"Bearer {HF_API_KEY}"},
        json={"inputs": texts, "options": {"wait_for_model": True}}
    )
    result = response.json()
    if isinstance(result, dict) and "error" in result:
        raise ValueError(f"HuggingFace API error: {result['error']}")
    return result


# ──────────────────────────────────────────────
# 3. STORAGE
# ──────────────────────────────────────────────

def store_knowledge(chunks_with_sources, embeddings):
    """Save chunks + embeddings + metadata to knowledge.json."""
    records = []
    for (text, source), emb in zip(chunks_with_sources, embeddings):
        records.append({
            "text":      text,
            "source":    source,
            "embedding": emb,
            "created":   date.today().isoformat()
        })
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return records


def load_knowledge():
    """Load existing knowledge base from disk."""
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# 4. RETRIEVAL — semantic search via cosine similarity
# ──────────────────────────────────────────────

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def retrieve(query, records, top_k=3):
    """Find the top-k most semantically similar chunks to the query."""
    query_emb = embed_texts([query])[0]
    scored = [
        (cosine_similarity(query_emb, r["embedding"]), r["text"], r["source"])
        for r in records
    ]
    scored.sort(reverse=True)
    return scored[:top_k]  # list of (score, text, source)


# ──────────────────────────────────────────────
# 5. ANSWER GENERATION
# ──────────────────────────────────────────────

def answer_query(query, top_results):
    """Generate a grounded answer using only the retrieved context."""
    context_block = "\n".join(
        f"[{source}] {text}" for _, text, source in top_results
    )
    prompt = f"""Answer the question using ONLY the notes below.
If the notes do not contain enough information, say so honestly.

Notes:
{context_block}

Question: {query}
"""
    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content


# ──────────────────────────────────────────────
# 6. MAIN CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Personal Knowledge Base Agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file",   help="Path to a single file (.txt, .md, .pdf, .docx)")
    group.add_argument("--folder", help="Path to a folder of notes")
    parser.add_argument("--reload", action="store_true",
                        help="Re-ingest files even if knowledge.json already exists")
    args = parser.parse_args()

    # ── Ingest or load ──
    if args.reload or not os.path.exists(KNOWLEDGE_FILE):
        print("\n📥 Ingesting notes...")
        chunks = ingest(file_path=args.file, folder_path=args.folder)
        if not chunks:
            print("No content found. Exiting.")
            return

        print(f"\n🔢 Embedding {len(chunks)} chunk(s)...")
        texts = [c[0] for c in chunks]
        embeddings = embed_texts(texts)
        records = store_knowledge(chunks, embeddings)
        print(f"✅ Knowledge base saved → {KNOWLEDGE_FILE}")
    else:
        print(f"\n📂 Loading existing knowledge base from {KNOWLEDGE_FILE}")
        print("   (run with --reload to re-ingest)")
        records = load_knowledge()

    print(f"   {len(records)} chunk(s) ready.\n")

    # ── Query loop ──
    while True:
        try:
            query = input("❓ Ask a question (or 'quit' to exit): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if query.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break
        if not query:
            continue

        top_results = retrieve(query, records)

        print("\n📎 Retrieved sources:")
        for score, text, source in top_results:
            print(f"   [{source}] (score: {score:.3f}) {text[:80]}...")

        answer = answer_query(query, top_results)
        print(f"\n💬 Answer:\n{answer}\n")
        print("─" * 60)


if __name__ == "__main__":
    main()