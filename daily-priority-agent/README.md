# Daily Task Prioritization Agent

A Python CLI agent that reads tasks from a CSV, scores them using a weighted formula, and outputs a structured daily plan — built as Day 1 of a personal AI agent learning series.

---

## What it does

- Reads tasks from `tasks.csv` (title, deadline, effort, impact, blocked status)
- Normalizes messy inputs like `"25m"`, `"L"`, `"yes"` into typed Python values
- Computes a priority score for every task using a configurable weighted formula
- Buckets tasks into: **Top 3**, **Next 5**, **Unblock**, and **Defer**
- Filters tasks to fit within your available time budget for the day
- Writes outputs to `plan.json` (structured) and `plan.txt` (human-readable)

---

## Project structure

```
daily-priority-agent/
├── agent.py        # Main agent — all logic lives here
├── tasks.csv       # Input: your task list
├── plan.json       # Output: structured plan (auto-generated)
├── plan.txt        # Output: human-readable plan (auto-generated)
└── README.md
```

---

## Quickstart

```bash
# 1. Clone and enter the folder
git clone https://github.com/YOUR_USERNAME/daily-priority-agent.git
cd daily-priority-agent

# 2. No dependencies — pure Python standard library
python3 --version   # needs 3.7+

# 3. Run
python3 agent.py
```

---

## Task format (`tasks.csv`)

```csv
title,description,deadline,effort,impact,blocked,tags
Send proposal to client,Finalize and email proposal,2025-12-22,25m,high,no,work
Fix login bug,Reproduce and patch issue,2025-12-24,L,high,no,work
Book dentist appointment,Call dentist office,,10m,low,no,personal
```

| Field | Accepted values |
|---|---|
| `deadline` | `YYYY-MM-DD` or blank |
| `effort` | `10m`, `25m`, `S` (15 min), `M` (45 min), `L` (90 min) |
| `impact` | `low`, `medium`, `high` |
| `blocked` | `yes` / `no` |

---

## Scoring formula

```
score = (urgency × W_urgency) + (impact × W_impact) + quickwin_bonus − blocked_penalty
```

| Signal | How it's computed | Default weight |
|---|---|---|
| Urgency | 0–5 based on days until deadline | 2.0 |
| Impact | low=1, medium=2, high=3 | 3.0 |
| Quick-win bonus | +1 if effort ≤ 15 min | 1.0 |
| Blocked penalty | −5 if task is blocked | 5.0 |

**Urgency scale:**

| Days until deadline | Urgency score |
|---|---|
| Overdue | 5.0 |
| Due today | 5.0 |
| Tomorrow | 4.0 |
| 2–3 days | 3.0 |
| 4–7 days | 2.0 |
| 8+ days | 1.0 |
| No deadline | 0.5 |

> The weights are a **ratio**, not an absolute scale. `urgency=2, impact=3` and `urgency=20, impact=30` produce identical rankings. Only the ratio between weights matters.

---

## Configuration

All tuneable constants are at the top of `agent.py`:

```python
WEIGHTS = {
    "urgency": 2.0,
    "importance": 3.0,
    "quickwin_bonus": 1.0,
    "blocked_penalty": 5.0,
}

AVAILABLE_MIN = 120   # your available time today in minutes
TOP3_COUNT = 3
NEXT5_COUNT = 5
```

### Formula presets

| Mode | urgency | importance | quickwin | Use when |
|---|---|---|---|---|
| Default (balanced) | 2.0 | 3.0 | 1.0 | Everyday use |
| Deadline-first | 5.0 | 1.0 | 0.5 | Exam / client crunch |
| Impact-first | 1.0 | 5.0 | 0.5 | Deep work / long projects |
| Quick-wins-first | 1.5 | 1.5 | 4.0 | Low-energy days / building momentum |

---

## Output example

```
Daily Task Prioritization Plan (2025-12-21)
=============================================

TOP 3 (Do these first)
----------------------
1. Send proposal to client  | deadline: 2025-12-22 | effort: 25m | score: 19.0
   Why: Due soon, High impact

2. Pay electricity bill  | deadline: 2025-12-22 | effort: 10m | score: 15.0
   Why: Due soon, Medium impact, Quick win

3. Prepare meeting agenda  | deadline: 2025-12-23 | effort: 30m | score: 17.0
   Why: Due soon, High impact

UNBLOCK (Blocked tasks)
-----------------------
1. Wait for design assets  | deadline: 2025-12-22 | effort: 15m | score: 10.0
   Why: Due soon, High impact, Blocked (needs unblock step)

TIME BUDGET (120 min available)
--------------------------------
  Tasks that fit: 3  |  Used: 65m  |  Remaining: 55m
```

---

## Concepts demonstrated

This project covers several core CS + software engineering ideas relevant to interviews:

- **Data pipeline pattern** — CSV → parse → normalize → score → sort → output. Each stage is isolated and testable.
- **Dataclasses** — using `@dataclass` as a typed value object (similar to a struct or record type).
- **Weighted linear scoring** — same math as a dot product / single-layer neural network neuron.
- **Greedy algorithm** — the time-budget selection is a greedy knapsack: pick highest-score tasks until the budget is full.
- **Separation of concerns** — parsers, scoring, bucketing, and rendering are all separate functions with no shared state.
- **Configuration over code** — `WEIGHTS` and `AVAILABLE_MIN` are top-level constants, not hardcoded inside logic.

---

## Potential improvements

- [ ] Knapsack-optimal time budget (instead of greedy)
- [ ] CLI flags: `--preset deadline-first`, `--available 90`
- [ ] Add `context` signal (home / work / commute) for location-aware prioritization
- [ ] Read tasks from Notion, Todoist, or Google Tasks via API
- [ ] Web UI with live score preview as you edit tasks
- [ ] Learn weights automatically from past "what did I actually do" data

---

## Part of

This is **Day 1** of a personal AI agent build series — focused on implementation fundamentals: data normalization, scoring formulas, and output generation without any external dependencies.

---

## License

MIT
