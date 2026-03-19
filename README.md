# SuperCharge SG — AI Customer Support Chatbot
**Challenge 1 · SuperCharge SG Build Challenge 2026**

> RAG-powered Telegram bot grounded in real SuperCharge SG knowledge.  
> **LLM:** Google Gemini · **Vector DB:** ChromaDB · **Leads:** Google Sheets · **Alerts:** Slack + Email

---

## Architecture Overview

![image_alt](https://github.com/Iguro02/supercharge-bot/blob/main/challenge2.drawio.png?raw=true)


---

## RAG Pipeline

### Knowledge Base Construction
- **Source:** `data/knowledge_base.txt` — all SuperCharge SG product, pricing, FAQ, regulatory content
- **Chunking:** Split on double-newlines (logical sections) → sliding window for long sections
- **Chunk size:** ~400 tokens with 50-token overlap
- **Embedding model:** `all-MiniLM-L6-v2` — free, runs locally, no API key needed
- **Vector store:** ChromaDB persistent client (stored in `chroma_db/`)
- **Retrieval:** Top-3 cosine-similarity chunks → injected into Gemini system prompt
- **FAQ strategy:** Q and A kept in one chunk so retrieval returns complete answers

### Why it doesn't hallucinate
Gemini is instructed via system prompt to answer **only** from the provided context chunks. If context is absent, the bot admits uncertainty and offers to escalate — never invents facts, prices, or specs.

---

## Intent Coverage

| Intent | Example Triggers | Action |
|--------|-----------------|--------|
| `greeting` | "hi", "hello", `/start` | Welcome message |
| `faq` | "what is TR25?", "how does ECIS work?" | RAG → Gemini |
| `price` | "how much does solar cost?", "pricing" | RAG → Gemini |
| `fault` | "my charger is broken", "report an error" | RAG → Gemini |
| `lead` | "I'm interested in solar", "get a quote" | Multi-turn capture → Google Sheets |
| `escalation` | "speak to a person", "human agent" | Slack + Email alert + handoff message |
| `unknown` ×3 | 3 consecutive unresolved queries | Auto-escalate |

---

## Setup Instructions

### 1. Clone & install dependencies

```bash
git clone https://github.com/YOUR_USERNAME/supercharge-bot.git
cd supercharge-bot
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Fill in your real values — see comments in .env.example
```

**Required:**
| Variable | Where to get it |
|----------|----------------|
| `TELEGRAM_BOT_TOKEN` | Message @BotFather on Telegram → `/newbot` |
| `GEMINI_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — free |
| `SLACK_WEBHOOK_URL` | [api.slack.com/apps](https://api.slack.com/apps) → Incoming Webhooks |
| `SMTP_USER` / `SMTP_PASS` | Gmail App Password (myaccount.google.com/apppasswords) |
| `ESCALATION_EMAIL_TO` | Email to receive handoff alerts (e.g. yusuf@supercharge.sg) |

**For lead capture (Google Sheets):**
| Variable | How |
|----------|-----|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GCP Console → Service Account → Download JSON → save to `credentials/` |
| `GOOGLE_SHEET_ID` | From Sheet URL: `docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit` |

> Share your Google Sheet with the service account's email address (Editor access).

### 3. Run locally

```bash
# Telegram bot
python bot_telegram.py

# WhatsApp bot (separate terminal — needs ngrok)
uvicorn bot_whatsapp:app --port 8000
ngrok http 8000
# Copy the ngrok HTTPS URL → Twilio console → WhatsApp Sandbox Settings → Webhook URL:
# https://xxxx.ngrok.io/whatsapp
```

### 4. Knowledge base builds automatically on first run
Or build manually:
```bash
python -c "from src.rag_pipeline import build_kb; build_kb()"
```

---

## Deployment — Railway.app (Recommended, Free Tier)

1. Push repo to GitHub
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub → select repo
3. Add all environment variables in the Railway dashboard
4. Railway detects `Dockerfile` and deploys automatically
5. Bot stays live 24/7 (no sleep on Railway Starter plan)


---

## Gmail App Password Setup (for Email Escalation)

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → 2-Step Verification → must be ON
3. Security → App passwords → Select app: Mail → Select device: Other → name it "SuperBot"
4. Copy the 16-character password → set as `SMTP_PASS` in `.env`

---

## Escalation Behaviour

When triggered (user says "speak to a person" OR 3 consecutive failed RAG lookups):

**Slack alert includes:**
- Chat ID and username
- Timestamp (UTC)
- Reason for escalation
- Last 3 conversation turns (formatted code block)

**Email alert includes:**
- Same information, HTML-formatted
- Sent to `ESCALATION_EMAIL_TO` (e.g. yusuf@supercharge.sg)

Both fire simultaneously. If one fails (e.g. Slack is down), the other still fires.

---

## Lead Capture Flow

```
User: "I'm interested in solar panels"
  → Bot: "What's your name?"
User: "Ahmad"
  → Bot: "Nice to meet you Ahmad! What's your email?"
User: "ahmad@email.com"
  → Bot: "What are you enquiring about? [1–5 options]"
User: "1"  (or "Solar Panel Installation")
  → Bot: "Thank you! Our team will reach out to ahmad@email.com shortly."
  → Google Sheet updated within seconds
```

Lead data saved: Timestamp, Name, Email, Enquiry Type, Platform (Telegram/WhatsApp), Chat ID

---

## Known Limitations

- **In-memory sessions:** Restart clears all sessions.
- **Gemini rate limits:** Free tier has 10 RPM (Request per Minute)  & 20 RPD (Request per Day). Sufficient for evaluation; upgrade for production.
- **Intent classifier:** Rule-based regex works well for known patterns. Edge cases (ambiguous phrasing) may hit `unknown`. A Gemini-based intent classifier call would handle these better.
- **Language:** English only. SuperCharge SG's Singapore audience may benefit from Mandarin/Malay support.
- **Railway Free Tier Limitation:**  Free tier deployment of Railway limits the use of GPU in Sentance Tranformer resorting to CPU due to Build Image Size Execeeding Quota, possibly limiting the full potential of RAG Retrieval. 

---

## File Structure

```
supercharge-bot/
├── bot_telegram.py          # Telegram bot entrypoint (run this)
├── requirements.txt
├── Dockerfile
├── railway.toml             # Railway.app deployment config
├── .env.example             # Copy to .env and fill in
├── .gitignore
├── data/
│   └── knowledge_base.txt   # Full SuperCharge SG KB (RAG source)
├── chroma_db/               # Auto-generated ChromaDB vector store
├── credentials/             # Place google_service_account.json here
│   └── .gitkeep
└── src/
    ├── __init__.py
    ├── rag_pipeline.py      # ChromaDB build + top-K retrieval
    ├── llm_client.py        # Google Gemini 1.5 Flash wrapper
    ├── intent.py            # Regex keyword intent classifier
    ├── leads.py             # Multi-turn lead capture + Google Sheets
    ├── escalation.py        # Slack webhook + SMTP email alerts
    └── session.py           # In-memory session manager (TTL 30 min)
```

---

## Evaluation Test Cases

These are the exact questions the evaluator will test — all are answered by the KB:

| Question | Expected source in KB |
|----------|----------------------|
| "What does a 5kWp solar system cost?" | Section A4 pricing table |
| "What is TR25?" | Section B1 |
| "Can I charge my EV overnight?" | Section G3 FAQ |
| "What is ECIS?" | Section B3 |
| "Do you cover HDB installations?" | Section G3 FAQ + A3 |
