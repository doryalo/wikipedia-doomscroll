# LearnScroll

> The doomscroll, but make it history.

Wikipedia's greatest stories, served like a social feed. Same infinite scroll,
same likes and comments, same dopamine loop — but every post is a real historical
moment narrated by the person who lived it.

![LearnScroll demo](https://github.com/doryalo/wikipedia-doomscroll/raw/main/demo.gif)

---

## How Codex & GPT-5.6 Power LearnScroll

LearnScroll is built on a two-stage AI enrichment pipeline that turns raw Wikipedia
articles into emotionally charged social posts in seconds.

### Stage 1 — Extraction (`gpt-5.6-luna`)

The cheaper, faster model reads a raw Wikipedia article and produces a structured
`ArticleDossier`:

- **Key facts** — each assigned a unique evidence ID for downstream grounding
- **Named entities** — people, places, institutions
- **Time periods** — with precision level (year / month / day / range / circa)
- **Human stakes** — what was actually at risk
- **Emotional dimensions** — anger, grief, awe, disbelief, fear, envy
- **Political & social dimensions** — power, conflict, systemic forces
- **Narrative material** — the hook that makes a story shareable
- **Engagement signals** — what will make someone stop scrolling
- **Sensitivity flags** — guardrails for responsible content

### Stage 2 — Synthesis & Post Generation (`gpt-5.6-terra`)

The stronger reasoning model takes the dossier and writes one social post:

- Punchy title (≤ 90 chars) + 25–45 word first-person body
- Picks a **dominant emotion** and makes every sentence intensify it
- Writes in the voice of the central historical figure
- Ends with an accusation, brutal contrast, or divisive question
- Returns the evidence IDs it used — any hallucinated ID is rejected at runtime

```python
# Every factual claim must cite a real evidence ID from the dossier
unknown_evidence = set(generated.evidence_ids) - {fact.id for fact in dossier.key_facts}
if unknown_evidence:
    raise ValueError(f"generated post references unknown evidence IDs: {sorted(unknown_evidence)}")
```

### Observability

Every LLM call is logged to SQLite:
- model, prompt version, reasoning effort
- input / output / cached / reasoning token counts
- latency (ms), estimated cost (USD), response ID

This lets us audit exactly what the pipeline spent, catch regressions in prompt
quality, and compare `gpt-5.6-luna` vs `gpt-5.6-terra` cost-to-quality tradeoffs.

### Pipeline trigger

The enrichment watcher monitors a directory. Drop any Wikipedia article JSON in —
the pipeline picks it up automatically, runs both stages, and publishes the post
to the live feed within seconds.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Tailwind CSS, Vite |
| Backend | FastAPI, Python, SQLite (WAL mode) |
| AI | OpenAI API — `gpt-5.6-luna` + `gpt-5.6-terra` |
| Schema validation | Pydantic (strict mode, `extra="forbid"`) |
| Content source | Wikipedia / Wikimedia Commons |
| Auth | SHA-256 + random salt password hashing |
| Pagination | Cursor-based (stable under concurrent writes) |

---

## Features

- **Year-range explorer** — timeline slider to pick any era, feed rebuilds instantly
- **Wikipedia portrait photos** — real Wikimedia Commons portraits as profile avatars
- **"On This Day" card** — deterministically surfaced post matched to today's date
- **Real social layer** — accounts, likes (with hover-to-see-who-liked popover), comments
- **Daily streak** — Duolingo-style habit loop for logged-in users
- **Topic chips** — one-click exploration by theme
- **Infinite scroll** — IntersectionObserver + cursor pagination

---

## Running locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Backend runs on `http://localhost:8000`. Frontend proxies `/api/*` there via Vite.

Demo accounts: `ada`, `sam`, `morgan`, `riley` — all with password `123`.

---

## Demo

- **Video:** https://github.com/doryalo/wikipedia-doomscroll/raw/main/demo.mov
- **GIF:** https://github.com/doryalo/wikipedia-doomscroll/raw/main/demo.gif
