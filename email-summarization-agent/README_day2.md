# Email Summarization Agent

A Python CLI agent that reads a raw email, sends it to an LLM, and outputs a structured summary with key points, action items, deadlines, urgency, and category classification — built as Day 2 of a personal AI agent learning series.

---

## What it does

- Reads email text from a `.txt` file
- Sends it to Groq's LLaMA model via an OpenAI-compatible API
- Extracts: summary, key points, action items, deadlines, urgency, category, sender, subject
- Validates the LLM's JSON output before saving
- Writes `summary.json` (structured) and `summary.txt` (human-readable)

---

## Project structure

```
email-summarization-agent/
├── agent.py        # All logic — read, call LLM, parse, validate, save
├── email.txt       # Input: paste your email here
├── .env            # Your API key — never commit this
├── .env.example    # Safe template to commit to GitHub
├── summary.json    # Output: structured (auto-generated)
├── summary.txt     # Output: human-readable (auto-generated)
└── README.md
```

---

## Quickstart

```bash
# 1. Install dependencies
pip install openai python-dotenv

# 2. Set your API key in .env
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# 3. Paste your email into email.txt

# 4. Run
python agent.py
```

---

## CLI flags

```bash
python agent.py --input emails/weekly.txt --json-out out.json --txt-out out.txt
```

| Flag | Default | Description |
|---|---|---|
| `--input` | `email.txt` | Path to the email file |
| `--json-out` | `summary.json` | Path for JSON output |
| `--txt-out` | `summary.txt` | Path for text output |

---

## Output schema (`summary.json`)

```json
{
  "summary": "2-3 sentence summary of the email",
  "key_points": ["point 1", "point 2"],
  "action_items": ["who does what"],
  "deadlines": ["date — description"],
  "urgency": "Low | Medium | High",
  "category": "Work | Personal | Finance | Newsletter | Alert",
  "sender": "name or null",
  "subject": "subject line or null",
  "processed_on": "YYYY-MM-DD"
}
```

---

## Sample output (`summary.txt`)

```
Email Summary  (2026-06-19)
============================================

Subject : Project Timeline Update
From    : Sarah
Urgency : [HIGH] High
Category : Work 

SUMMARY
-------
Sarah notified the team that the client moved the prototype deadline
from March 20 to March 10, requiring design assets by March 5.
Engineering is asked to prioritize API integration this week.

KEY POINTS
----------
  • Client moved prototype deadline from March 20 to March 10
  • Design must finalize assets by March 5
  • Engineering should prioritize API integration this week
  • Team sync scheduled for Friday

ACTION ITEMS
------------
  • Design team: finalize all assets by March 5
  • Engineering team: prioritize API integration this week
  • All: flag concerns to Sarah before Friday

DEADLINES
---------
  • March 5 — Design assets finalized
  • March 10 — Prototype delivered to client
  • Friday — Progress sync meeting
```

---

## How the prompt engineering works

The system prompt does four things:

1. **Role** — "You are an Email Summarization Agent" sets context and persona
2. **Numbered tasks** — explicit list leaves no room for ambiguity
3. **Output schema** — exact JSON shape with field names and allowed values
4. **Format constraint** — "Return ONLY valid JSON" prevents markdown wrapping

The `parse_response()` function strips accidental ` ```json ``` ` fences anyway — LLMs sometimes wrap JSON in markdown even when told not to. `validate_output()` then checks every required key and coerces wrong types silently.

---

## Category classification

Added as an improvement on the base implementation. The `category` field classifies each email automatically:

| Value | When assigned |
|---|---|
| `Work` | Project updates, team communication, client emails |
| `Personal` | Friends, family, social plans |
| `Finance` | Bills, invoices, bank notifications |
| `Newsletter` | Subscriptions, marketing, announcements |
| `Alert` | Automated system notifications, security alerts |

Implementation: one extra task in `SYSTEM_PROMPT` and one extra field in the JSON schema — no code changes required. Demonstrates how much behaviour you can add through prompt engineering alone.

---

## Swapping LLM providers

Only `call_llm()` needs to change. Everything else — parsing, validation, saving — is identical.

**Current: Groq (free, fast)**
```python
from openai import OpenAI
_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
GROQ_MODEL = "openai/gpt-oss-120b"

def call_llm(system_prompt, user_message):
    r = _client.chat.completions.create(
        model=GROQ_MODEL, temperature=0.2,
        messages=[{"role":"system","content":system_prompt},
                  {"role":"user","content":user_message}]
    )
    return r.choices[0].message.content
```

**Swap to Gemini (free)**
```python
from google import genai
from google.genai import types
_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def call_llm(system_prompt, user_message):
    r = _client.models.generate_content(
        model="gemini-1.5-flash", contents=user_message,
        config=types.GenerateContentConfig(system_instruction=system_prompt)
    )
    return r.text
```

**Swap to Anthropic Claude**
```python
import anthropic
_client = anthropic.Anthropic()

def call_llm(system_prompt, user_message):
    r = _client.messages.create(
        model="claude-sonnet-4-6", max_tokens=1024,
        system=system_prompt,
        messages=[{"role":"user","content":user_message}]
    )
    return r.content[0].text
```

---

## Free Groq models

Change `GROQ_MODEL` at the top of `agent.py` to switch:

| Model string | Notes |
|---|---|
| `llama-3.3-70b-versatile` | Best quality — recommended |
| `llama-3.1-8b-instant` | Fastest, lightest |
| `mixtral-8x7b-32768` | Long context (32k tokens) |
| `gemma2-9b-it` | Google Gemma, very fast |

---

## Concepts demonstrated

- **Prompt engineering** — role assignment, task decomposition, schema-constrained output
- **LLM as a function** — `call_llm(system, user) → str` is a pure interface; swap providers without touching logic
- **Provider abstraction** — one function swap changes the entire backend (Groq → Gemini → Claude)
- **Defensive JSON parsing** — strip markdown fences, validate schema, safe type coercion
- **Fail fast vs fail silent** — crash on missing keys (critical), fix silently on wrong types (recoverable)
- **CLI with argparse** — configurable inputs and outputs without editing source code
- **Environment variable management** — `.env` + `python-dotenv`, never hardcode secrets

---

## Potential improvements

- [ ] Batch mode: `--folder ./inbox/` to summarize multiple emails at once
- [ ] History logging: append each run to `history.csv` for inbox pattern analysis
- [ ] Draft reply: second LLM call generates a suggested response
- [ ] Connect to Day 1: pipe High urgency action items into `tasks.csv`
- [ ] Gmail API integration: read directly from your real inbox
- [ ] SQLite storage: replace file outputs with a queryable database

---

## Part of

This is **Day 2** of a personal AI agent build series.

| Day | Agent | Key concept |
|---|---|---|
| 1 | Daily Task Prioritization | Weighted scoring, greedy algorithm, pure Python |
| 2 | Email Summarization | LLM integration, prompt engineering, provider abstraction |

---

## Environment setup

```bash
# .env (never commit — add to .gitignore)
GROQ_API_KEY=gsk_your_key_here

# .env.example (safe to commit)
GROQ_API_KEY=
```

```
# .gitignore
.env
summary.json
summary.txt
__pycache__/
*.pyc
```

---

## License

MIT
