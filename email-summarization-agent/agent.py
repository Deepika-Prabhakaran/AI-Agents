import json
import os
import argparse
from datetime import date

from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────
# LLM backend — swap this block to switch
# providers (OpenAI, Gemini, local LLM)
# ─────────────────────────────────────────
from openai import OpenAI

_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
GROQ_MODEL = "openai/gpt-oss-120b"  # fast, free, reliable on Groq

def call_llm(system_prompt: str, user_message: str) -> str:
    """Call Groq and return raw response text."""
    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    return response.choices[0].message.content

# ─────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an Email Summarization Agent.

Your job:
1. Summarize the email in 2-3 sentences
2. Extract key points as a list
3. Extract action items (who should do what, be specific)
4. Identify all deadlines mentioned
5. Classify urgency: Low, Medium, or High
6. Classify caetgory: Work| Personal | Finance | Newsletter | Alert 

Return ONLY valid JSON — no markdown fences, no extra text — with exactly this schema:

{
  "summary": "string",
  "key_points": ["string"],
  "action_items": ["string"],
  "deadlines": ["string"],
  "urgency": "Low | Medium | High",
  "category":"Work | Personal | Finance | Newsletter | Alert",
  "sender": "string or null",
  "subject": "string or null"
}
""".strip()

# ─────────────────────────────────────────
# Required output keys for validation
# ─────────────────────────────────────────
REQUIRED_KEYS = {"summary", "key_points", "action_items", "deadlines", "urgency","category"}


# ─────────────────────────────────────────
# Core functions
# ─────────────────────────────────────────
def read_email(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Email file not found: '{path}'\n"
            f"Create it or pass a different path with --input"
        )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        raise ValueError(f"Email file is empty: '{path}'")
    return content


def parse_response(raw: str) -> dict:
    """Parse LLM response, stripping accidental markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON.\nError: {e}\nRaw response:\n{raw}"
        )
    return data


def validate_output(data: dict) -> dict:
    """Check all required keys exist and types are correct."""
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM response missing keys: {missing}")

    for field in ("key_points", "action_items", "deadlines"):
        if not isinstance(data[field], list):
            data[field] = [str(data[field])]

    valid_urgency = {"Low", "Medium", "High"}
    if data["urgency"] not in valid_urgency:
        data["urgency"] = "Medium"

    category={"Work","Personal","Finance","Newsletter","Alert"}
    if data["category"] not in category:
        data["category"]="Alert"
    return data


def summarize_email(email_text: str) -> dict:
    """Main pipeline: call LLM → parse → validate."""
    print("Calling LLM...")
    raw = call_llm(SYSTEM_PROMPT, email_text)
    print("Parsing response...")
    data = parse_response(raw)
    data = validate_output(data)
    data["processed_on"] = date.today().isoformat()
    return data


def save_outputs(data: dict, json_path: str, txt_path: str):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Email Summary  ({data['processed_on']})\n")
        f.write("=" * 44 + "\n\n")

        if data.get("subject"):
            f.write(f"Subject : {data['subject']}\n")
        if data.get("sender"):
            f.write(f"From    : {data['sender']}\n")
        if data.get("subject") or data.get("sender"):
            f.write("\n")

        f.write(f"Urgency : {data['urgency']}\n\n")

        f.write(f"category : {data['category']}\n\n")

        f.write("SUMMARY\n")
        f.write("-" * 7 + "\n")
        f.write(data["summary"] + "\n\n")

        f.write("KEY POINTS\n")
        f.write("-" * 10 + "\n")
        for p in data["key_points"]:
            f.write(f"  • {p}\n")

        f.write("\nACTION ITEMS\n")
        f.write("-" * 12 + "\n")
        for a in data["action_items"]:
            f.write(f"  • {a}\n")

        f.write("\nDEADLINES\n")
        f.write("-" * 9 + "\n")
        if data["deadlines"]:
            for d in data["deadlines"]:
                f.write(f"  • {d}\n")
        else:
            f.write("  (none mentioned)\n")


def render_console(data: dict):
    urgency_icons = {"High": "[HIGH]", "Medium": "[MED]", "Low": "[LOW]"}
    icon = urgency_icons.get(data["urgency"], "•")

    print("\n" + "=" * 44)
    print(f"  Email Summary  ({data['processed_on']})")
    print("=" * 44)
    if data.get("subject"):
        print(f"  Subject : {data['subject']}")
    if data.get("sender"):
        print(f"  From    : {data['sender']}")
    print(f"  Urgency : {icon} {data['urgency']}")
    print()

    print("SUMMARY")
    print("  " + data["summary"])
    print()

    print("KEY POINTS")
    for p in data["key_points"]:
        print(f"  • {p}")
    print()

    print("ACTION ITEMS")
    for a in data["action_items"]:
        print(f"  • {a}")
    print()

    print("DEADLINES")
    if data["deadlines"]:
        for d in data["deadlines"]:
            print(f"  • {d}")
    else:
        print("  (none mentioned)")
    print()


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Summarize an email using an LLM"
    )
    parser.add_argument(
        "--input", default="email.txt",
        help="Path to the email text file (default: email.txt)"
    )
    parser.add_argument(
        "--json-out", default="summary.json",
        help="Path for JSON output (default: summary.json)"
    )
    parser.add_argument(
        "--txt-out", default="summary.txt",
        help="Path for text output (default: summary.txt)"
    )
    args = parser.parse_args()

    email_text = read_email(args.input)
    print(f"Read email from '{args.input}' ({len(email_text)} chars)")

    result = summarize_email(email_text)

    save_outputs(result, args.json_out, args.txt_out)
    print(f"\nSaved: {args.json_out}")
    print(f"Saved: {args.txt_out}")

    render_console(result)


if __name__ == "__main__":
    main()