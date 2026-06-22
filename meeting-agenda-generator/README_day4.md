# Meeting Agenda Generator Agent

A Python CLI agent that reads a meeting brief, sends it to an LLM, and outputs a structured, time-boxed meeting agenda with validation and ASCII time bars — built as Day 3 of a personal AI agent learning series.

---

## What it does

- Reads a meeting brief from a `.txt` file (objective, attendees, duration, topics)
- Sends it to Groq's LLaMA model with a structured prompt
- Parses and validates the LLM's JSON output — checks required fields, item structure, and time consistency
- Renders an ASCII time bar per agenda item showing how each topic fills the meeting
- Writes `agenda.json` (structured) and `agenda.txt` (human-readable)
- Shows LLM response time and time budget summary in the terminal

---

## Project structure

```
meeting-agenda-agent/
├── agent.py        # All logic — read, call LLM, parse, validate, save
├── meeting.txt     # Input: paste your meeting brief here
├── .env            # Your API key — never commit this
├── .env.example    # Safe template to commit to GitHub
├── .gitignore      # Excludes .env, agenda.json, agenda.txt
├── agenda.json     # Output: structured agenda (auto-generated)
├── agenda.txt      # Output: human-readable agenda (auto-generated)
└── README.md
```

---

## Quickstart

```bash
# 1. Install dependencies
pip install openai python-dotenv

# 2. Set your API key
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# 3. Paste your meeting brief into meeting.txt
# 4. Run
python agent.py
```

---

## CLI flags

```bash
python agent.py --input standup.txt --json-out standup.json --txt-out standup.txt
```

| Flag | Default | Description |
|---|---|---|
| `--input` | `meeting.txt` | Path to the meeting brief file |
| `--json-out` | `agenda.json` | Path for JSON output |
| `--txt-out` | `agenda.txt` | Path for text output |

---

## Input format (`meeting.txt`)

Write your meeting brief in plain English:

```
Meeting: Q1 Planning Session
Duration: 60 minutes
Attendees: Deepika, Sarah, Raj, Priya
Objective: Review Q1 goals and assign ownership for each initiative

Topics to cover:
- Q4 retrospective (what worked, what didn't)
- Q1 OKR review and gap analysis
- Initiative ownership assignments
- Blockers and dependencies
- Next steps and timeline
```

---

## Output schema (`agenda.json`)

```json
{
  "meeting_title": "Q1 Planning Session",
  "objective": "Review Q1 goals and assign ownership for each initiative",
  "total_duration_minutes": 60,
  "generated_on": "2026-06-19",
  "agenda": [
    {
      "topic": "Q4 Retrospective",
      "time_minutes": 10,
      "owner": "Deepika",
      "outcome": "Shared understanding of what worked and what to improve"
    }
  ]
}
```

---

## Sample output (`agenda.txt`)

```
Meeting Agenda  (2026-06-19)
================================================

Title     : Q1 Planning Session
Objective : Review Q1 goals and assign ownership for each initiative
Duration  : 60 minutes

AGENDA
------
1. Q4 Retrospective (10 min)  [===                 ]
   Owner  : Deepika
   Outcome: Shared understanding of what worked and what to improve

2. Q1 OKR Review (15 min)  [=====               ]
   Owner  : Sarah
   Outcome: Identified gaps and priorities for the quarter

3. Initiative Ownership (15 min)  [=====               ]
   Owner  : Raj
   Outcome: Each initiative has a clear owner and accountability

4. Blockers and Dependencies (10 min)  [===                 ]
   Owner  : All
   Outcome: Known blockers documented, escalation path agreed

5. Next Steps and Timeline (10 min)  [===                 ]
   Owner  : Priya
   Outcome: Action items assigned with clear deadlines

------------------------------------------------
Time used : 60/60 min  (fully allocated)
```

---

## Validation — what gets checked

The `validate()` function runs five checks after every LLM response:

| Check | Behaviour |
|---|---|
| Required top-level keys present | Crashes loudly with missing key names |
| `agenda` is a non-empty list | Crashes with clear message |
| Every item has required fields | Crashes with item number that failed |
| `time_minutes` is a positive number | Fixes silently — defaults to 5 min |
| Total time vs stated duration | Warns in terminal, does not crash |

The rule: crash loudly on structural failures, fix silently on minor type issues, warn on consistency problems.

---

## Error handling

| Scenario | What happens |
|---|---|
| `meeting.txt` not found | `FileNotFoundError` with helpful message and `--input` hint |
| `meeting.txt` is empty | `ValueError` before wasting an API call |
| LLM returns JSON wrapped in ` ```json ``` ` | Fences are stripped automatically |
| LLM returns invalid JSON | `ValueError` with raw response shown for debugging |
| LLM skips a required field | `ValueError` crashes immediately with field names |
| LLM agenda items exceed duration | Warning printed — output still saved |

---

## How the prompt works

The system prompt does three things:

1. **Role** — "You are a Meeting Agenda Generator Agent" sets context
2. **Rules** — explicit numbered constraints (fit duration, include owners, identify decisions)
3. **Output contract** — exact JSON schema with field names and types

`temperature=0.3` is slightly higher than `0.2` used in the email agent — agendas benefit from slightly more creative topic structuring while still being consistent.

---

## LLM provider

Uses Groq's free API with `llama-3.3-70b-versatile` via the OpenAI-compatible SDK:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
GROQ_MODEL = "openai/gpt-oss-120b"
```

To switch providers, only the client block changes — `parse_response`, `validate`, `save_outputs`, and `render_console` are identical regardless of provider.

**Active free Groq models:**

| Model | Notes |
|---|---|
| `llama-3.3-70b-versatile` | Best quality — recommended |
| `llama-3.1-8b-instant` | Fastest, lightest |
| `mixtral-8x7b-32768` | Long context (32k tokens) |
| `gemma2-9b-it` | Google Gemma, very fast |

---

## Architecture — one function, one job

| Function | Job |
|---|---|
| `read_input()` | Load and guard the input file |
| `call_llm()` | Talk to Groq, return raw string |
| `parse_response()` | Strip fences, parse JSON |
| `validate()` | Check structure and consistency |
| `generate_agenda()` | Orchestrate: call → parse → validate |
| `time_bar()` | Render ASCII time bar string |
| `save_outputs()` | Write JSON and TXT files |
| `render_console()` | Pretty-print to terminal |
| `main()` | CLI flags, top-level orchestration |

Each function has exactly one job and no shared state. Swapping the output format (e.g. HTML instead of TXT) means changing only `save_outputs()`.

---

## Concepts demonstrated

- **Prompt engineering** — role + rules + output schema as a structured contract with the LLM
- **Defensive JSON parsing** — strip markdown fences, validate schema, safe type coercion
- **Two-tier error strategy** — crash loudly on structural failures, fix silently on recoverable ones
- **Provider abstraction** — `call_llm()` is the only function that knows which LLM is being used
- **CLI with argparse** — configurable inputs and outputs without editing source code
- **Observability** — LLM response time and time budget summary printed on every run
- **ASCII time bars** — visual representation of agenda proportions without any dependencies

---

## Environment setup

```bash
# .env  (never commit)
GROQ_API_KEY=gsk_your_key_here

# .env.example  (safe to commit)
GROQ_API_KEY=

# .gitignore
.env
agenda.json
agenda.txt
__pycache__/
*.pyc
```

---

## Potential improvements

- [ ] Self-critique loop: second LLM call reviews the agenda for gaps before saving
- [ ] Generate notes template: pre-filled `notes.md` with each agenda item as a section
- [ ] History logging: append each run to `history.csv` for pattern analysis
- [ ] Export as `.ics` calendar file for Google Calendar / Outlook
- [ ] Connect to Day 1: write agenda items with owners into `tasks.csv` as follow-up tasks
- [ ] Connect to Day 2: feed email action items directly into `meeting.txt`
- [ ] Unit tests: `validate()`, fence stripping, and time bar rendering with no API calls

---

## Part of

This is **Day 3** of a personal AI agent build series.

| Day | Agent | Key concept |
|---|---|---|
| 1 | Daily Task Prioritization | Weighted scoring, greedy algorithm, pure Python |
| 2 | Email Summarization | LLM integration, prompt engineering, provider abstraction |
| 3 | Calendar Conflict Resolver | Deterministic conflict detection, rule-based resolution |
| 4 | Meeting Agenda Generator | Structured LLM output, validation, error handling, time bars |

---

## License

MIT
