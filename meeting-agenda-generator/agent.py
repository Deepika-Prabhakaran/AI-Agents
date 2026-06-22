import json
import os
import argparse
import time
from datetime import date
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ─────────────────────────────────────────
# LLM backend
# ─────────────────────────────────────────
_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
GROQ_MODEL = "openai/gpt-oss-120b"
# ─────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are a Meeting Agenda Generator Agent.

Your job is to generate a clear, time-boxed meeting agenda.

Rules:
- Agenda must fit within the provided duration
- Focus on the meeting objective
- Include time allocation for each item
- Identify decision points where applicable
- Return ONLY valid JSON — no markdown fences, no extra text — with exactly this schema:

{
  "meeting_title": "string",
  "objective": "string",
  "total_duration_minutes": 0,
  "agenda": [
    {
      "topic": "string",
      "time_minutes": 0,
      "owner": "string",
      "outcome": "string"
    }
  ]
}
""".strip()

# ─────────────────────────────────────────
# Required keys for validation
# ─────────────────────────────────────────
REQUIRED_KEYS = {"meeting_title", "objective", "total_duration_minutes", "agenda"}
REQUIRED_ITEM_KEYS = {"topic", "time_minutes", "owner", "outcome"}


# ─────────────────────────────────────────
# Core functions
# ─────────────────────────────────────────
def read_input(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Meeting brief not found: '{path}'\n"
            f"Create it or pass a different path with --input"
        )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        raise ValueError(f"Meeting file is empty: '{path}'")
    return content


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call Groq and return raw response text."""
    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    return response.choices[0].message.content


def parse_response(raw: str) -> dict:
    """Parse LLM response, stripping accidental markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON.\nError: {e}\nRaw response:\n{raw}"
        )


def validate(data: dict) -> dict:
    """Check required keys, types, and time consistency."""

    # 1 — required top-level keys
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM response missing keys: {missing}")

    # 2 — agenda must be a non-empty list
    if not isinstance(data["agenda"], list) or len(data["agenda"]) == 0:
        raise ValueError("'agenda' must be a non-empty list")

    # 3 — every agenda item must have required keys
    for i, item in enumerate(data["agenda"]):
        missing_item = REQUIRED_ITEM_KEYS - set(item.keys())
        if missing_item:
            raise ValueError(f"Agenda item {i+1} missing keys: {missing_item}")

    # 4 — time_minutes must be a positive int in every item
    for i, item in enumerate(data["agenda"]):
        if not isinstance(item["time_minutes"], (int, float)) or item["time_minutes"] <= 0:
            data["agenda"][i]["time_minutes"] = 5  # safe fallback

    # 5 — total time consistency check (warn, don't crash)
    allocated = sum(item["time_minutes"] for item in data["agenda"])
    total = data.get("total_duration_minutes", 0)
    if allocated > total:
        print(
            f"Warning: agenda items total {allocated} min "
            f"but meeting duration is {total} min. "
            f"Consider shortening some items."
        )

    # 6 — total_duration_minutes must be a positive number
    if not isinstance(total, (int, float)) or total <= 0:
        data["total_duration_minutes"] = allocated  # infer from items

    return data


def generate_agenda(meeting_text: str) -> dict:
    """Main pipeline: call LLM → parse → validate."""
    print("Calling LLM...")
    start = time.time()
    raw = call_llm(SYSTEM_PROMPT, meeting_text)
    elapsed = time.time() - start
    print(f"LLM responded in {elapsed:.2f}s")

    print("Parsing response...")
    data = parse_response(raw)

    print("Validating output...")
    data = validate(data)

    data["generated_on"] = date.today().isoformat()
    return data


def time_bar(minutes: int, total: int, width: int = 20) -> str:
    """Render a simple ASCII time bar."""
    filled = max(1, round((minutes / total) * width)) if total > 0 else 1
    return "[" + "=" * filled + " " * (width - filled) + "]"


def save_outputs(data: dict, json_path: str, txt_path: str):
    # JSON — structured, automation-ready
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    total = data["total_duration_minutes"]
    allocated = sum(item["time_minutes"] for item in data["agenda"])

    # TXT — human readable
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Meeting Agenda  ({data['generated_on']})\n")
        f.write("=" * 48 + "\n\n")
        f.write(f"Title     : {data['meeting_title']}\n")
        f.write(f"Objective : {data['objective']}\n")
        f.write(f"Duration  : {total} minutes\n\n")

        f.write("AGENDA\n")
        f.write("-" * 6 + "\n")
        for i, item in enumerate(data["agenda"], 1):
            bar = time_bar(item["time_minutes"], total)
            f.write(f"{i}. {item['topic']} ({item['time_minutes']} min)  {bar}\n")
            f.write(f"   Owner  : {item['owner']}\n")
            f.write(f"   Outcome: {item['outcome']}\n\n")

        f.write("-" * 48 + "\n")
        f.write(f"Time used : {allocated}/{total} min")
        remaining = total - allocated
        if remaining > 0:
            f.write(f"  ({remaining} min buffer)\n")
        elif remaining < 0:
            f.write(f"  (over by {abs(remaining)} min — review items)\n")
        else:
            f.write("  (fully allocated)\n")


def render_console(data: dict):
    """Pretty-print agenda to terminal."""
    total = data["total_duration_minutes"]
    allocated = sum(item["time_minutes"] for item in data["agenda"])

    print("\n" + "=" * 48)
    print(f"  Meeting Agenda  ({data['generated_on']})")
    print("=" * 48)
    print(f"  Title     : {data['meeting_title']}")
    print(f"  Objective : {data['objective']}")
    print(f"  Duration  : {total} min\n")

    print("AGENDA")
    print("-" * 6)
    for i, item in enumerate(data["agenda"], 1):
        bar = time_bar(item["time_minutes"], total)
        print(f"{i}. {item['topic']} ({item['time_minutes']} min)  {bar}")
        print(f"   Owner  : {item['owner']}")
        print(f"   Outcome: {item['outcome']}\n")

    print("-" * 48)
    remaining = total - allocated
    if remaining > 0:
        print(f"  Time used: {allocated}/{total} min  ({remaining} min buffer)")
    elif remaining < 0:
        print(f"  Time used: {allocated}/{total} min  (over by {abs(remaining)} min)")
    else:
        print(f"  Time used: {allocated}/{total} min  (fully allocated)")
    print()


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate a meeting agenda using an LLM"
    )
    parser.add_argument(
        "--input", default="meeting.txt",
        help="Path to meeting brief file (default: meeting.txt)"
    )
    parser.add_argument(
        "--json-out", default="agenda.json",
        help="Path for JSON output (default: agenda.json)"
    )
    parser.add_argument(
        "--txt-out", default="agenda.txt",
        help="Path for text output (default: agenda.txt)"
    )
    args = parser.parse_args()

    # Read
    meeting_text = read_input(args.input)
    print(f"Read meeting brief from '{args.input}' ({len(meeting_text)} chars)")

    # Generate
    agenda = generate_agenda(meeting_text)

    # Save
    save_outputs(agenda, args.json_out, args.txt_out)
    print(f"\nSaved: {args.json_out}")
    print(f"Saved: {args.txt_out}")

    # Display
    render_console(agenda)


if __name__ == "__main__":
    main()