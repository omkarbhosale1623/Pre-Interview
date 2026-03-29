# Pre-Interview

<img width="1428" height="660" alt="image" src="https://github.com/user-attachments/assets/8ab03c6d-99e1-4d78-9db4-cd29aac70617" />

> Speech-to-speech AI interview platform. Upload a question bank → conduct a live spoken interview → receive an AI-powered evaluation report. Three-phase roadmap from working PoC to enterprise-grade multi-tenant SaaS.

---

## Roadmap — three phases

### Phase 1 · current state (MVP — HTTP, single-tenant, SQLite)

**What is built and working:**

- Recruiter auth (signup / signin / JWT session)
- Question bank upload (CSV, JSON, TXT, DOCX)
- Interview scheduling — immediate link or date/time-gated link with 30-min expiry window
- Invite email via SMTP (Gmail or any SMTP provider)
- Speech-to-speech interview loop: Whisper STT → LLM acknowledgement skipped (instant) → ElevenLabs TTS
- TTS pre-caching — Q2 onwards has near-zero audio delay (~0.2 s vs ~1.5 s for Q1)
- Interview state machine: `waiting → active → completed → evaluated`
- Per-session `asyncio.Lock` prevents double-processing from React StrictMode / double-mount
- AI evaluation via OpenRouter (Gemini 2.5 Flash primary, LLaMA 70B fallback) with per-question score, rating, strengths, improvements, detailed feedback, communication assessment
- Evaluation report emailed to recruiter (HTML + plain-text) including full Q&A transcript
- Thank-you email to candidate
- Light/dark theme toggle backed by CSS variables

**What is NOT yet in Phase 1:**

- No multi-tenancy — all data is in a single SQLite file with no org separation
- No resume or JD parsing
- No AI question generation
- No follow-up questions
- No video proctoring or emotion detection
- No real-time WebRTC — HTTP request-response only, no barge-in
- No LiveKit or PipeCAT
- No horizontal scaling beyond ~20 concurrent interviews

---

### Phase 2 · production SaaS (next milestone)

**What Phase 2 adds:**

Multi-tenancy is the first and most critical addition — add `org_id` to every DB table, a `tenants` table, and JWT claims carrying `org_id`. Every query gets a `WHERE org_id = ?` guard. This must be done before anything else as it is the hardest thing to retrofit.

Resume parsing uses `pdfminer.six` + `python-docx` for extraction, then an LLM call to produce structured JSON (name, skills, experience, education). JD text goes through the same LLM extraction to pull required skills. Both are stored in Postgres enabling skill-gap analysis at evaluation time.

AI question generation calls the LLM with `{resume_summary} + {jd_skills}` and asks for 8 targeted questions as JSON, cached per `(resume_hash, jd_hash)` to avoid regenerating for the same pair.

Follow-up logic: each `AnswerEntry` gains a `follow_up_count` field. After recording an answer, if `follow_up_count < 2` and the answer is incomplete (below a confidence threshold), a follow-up is pushed onto a session-level queue before advancing `current_question_index`.

Replace SQLite → Postgres (`asyncpg` + SQLAlchemy 2.0), add S3 for resume/audio blobs, Redis for shared TTS cache (survives restarts), Celery for async evaluation jobs.

**Target scale:** 50–200 concurrent interviews, single FastAPI cluster + Postgres + Redis + S3 + Celery workers.

---

### Phase 3 · enterprise ML + video (future)

**Why LiveKit and PipeCAT enter here:**

Phase 1 and 2 use HTTP request-response. The specific capability that requires LiveKit is sub-200ms barge-in — the candidate interrupts the AI mid-sentence and the system responds without a 1–2 s HTTP round trip. PipeCAT runs on top of LiveKit as a server-side pipeline: VAD → Whisper STT → LLM → TTS → back to candidate in a single streaming loop.

**What Phase 3 adds:**

- LiveKit Cloud SFU — WebRTC media server, one room per session
- PipeCAT server-side voice agent — replaces the HTTP speech pipeline
- MediaPipe face mesh — client-side (or sidecar container) for gaze tracking, face count, object detection
- Audio ML — prosody analysis, emotion detection, confidence scoring, stress markers
- Kafka event bus — proctoring events stream from MediaPipe to Kafka topics
- Spark Streaming — consumes Kafka, writes aggregated signals to data warehouse
- BigQuery / Delta Lake — interview analytics, model training data
- ML scoring pipeline — embedding-based answer relevance, semantic similarity, skill gap model, fraud signal aggregator, candidate ranking
- LLM fine-tuning loop — recruiter decisions feed back into question generation model
- Kubernetes — horizontal scaling to 1000+ concurrent interviews
- SOC2/GDPR compliance — audit logs, PII masking in transcripts, WAF, SIEM

---

## Repository structure

```
pre-interview-poc/
├── backend/
│   ├── main.py                    # FastAPI app, startup pre-warm
│   ├── config.py                  # Settings (env vars via pydantic-settings)
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/
│   │   └── schemas.py             # All Pydantic models and enums
│   ├── services/
│   │   ├── postgres_store.py     # PostgreSQL persistence (Neon/Cloud)
│   │   ├── session_store.py      # Re-exports store (uses Postgres)
│   │   ├── question_service.py    # CSV / JSON / DOCX / TXT parser
│   │   ├── ai_evaluator.py        # LLM evaluation engine (OpenRouter)
│   │   ├── conversation_service.py# LangGraph state graph — instant, no LLM in RT path
│   │   ├── email_service.py       # SMTP invite + report + thank-you emails
│   │   └── speech_service.py      # Whisper STT + ElevenLabs / OpenAI TTS
│   └── routers/
│       ├── auth.py                # Recruiter signup / signin / signout / me
│       ├── questions.py           # Upload + list question banks
│       ├── interview.py           # Session lifecycle + conversation step (TTS pre-cache)
│       ├── evaluation.py          # Trigger + retrieve AI evaluation
│       ├── report.py              # JSON + plain-text report download
│       ├── scheduling.py          # Schedule interview + join by token
│       └── speech.py              # /transcribe (Whisper) + /tts (ElevenLabs)
│
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                # Top-level flow manager (step state machine)
│       ├── main.jsx               # Entry point + global CSS variables
│       ├── services/
│       │   └── api.js             # Unified API client (all fetch calls)
│       ├── hooks/
│       │   └── useSpeech.js       # STT recording + silence detection + TTS player
│       └── components/
│           ├── Auth.jsx           # Recruiter login + signup forms
│           ├── UploadBank.jsx     # Question bank upload + candidate details
│           ├── ScheduleInterview.jsx  # Schedule later (date/time picker)
│           ├── InterviewRoom.jsx  # Live voice interview UI
│           ├── Report.jsx         # AI evaluation report + thank-you screen
│           └── ThankYou.jsx       # Candidate completion screen
│
├── sample_questions.csv
├── sample_questions.json
└── README.md
```

---

## Quick start

### 1. Backend

```bash
cd backend

# Create and activate virtualenv
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — required keys listed below

# Run (auto-reloads, pre-warms Whisper at startup)
uvicorn main:app --reload
# http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

### 3. Workflow

1. Open `http://localhost:5173` — sign up as a recruiter.
2. Upload a question bank (CSV/JSON) or select an existing one.
3. Enter candidate name, email, and role.
4. Click **Send Link** (immediate) or **Schedule Later** (date/time-gated, 30-min window).
5. Candidate opens the unique link — the AI interviewer greets them and asks questions via speech.
6. After all questions, the AI evaluation runs automatically and the report is emailed to the recruiter.
7. Candidate receives a thank-you email.

---

## Environment variables

Create `backend/.env` from `.env.example` and fill in:

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | Yes | OpenRouter API key (get one at openrouter.ai) |
| `LLM_MODEL` | No | Primary LLM model (default: `google/gemini-2.5-flash`) |
| `ELEVENLABS_API_KEY` | Yes (for TTS) | ElevenLabs API key for voice synthesis |
| `OPENAI_API_KEY` | No | OpenAI key used as TTS fallback if ElevenLabs fails |
| `SMTP_SERVER` | No | SMTP host (default: `smtp.gmail.com`) |
| `SMTP_PORT` | No | SMTP port (default: `587`) |
| `SMTP_USERNAME` | No | SMTP login email address |
| `SMTP_PASSWORD` | No | SMTP password or app password |
| `EMAIL_FROM` | No | Sender address (defaults to `SMTP_USERNAME`) |
| `APP_BASE_URL` | No | Frontend base URL for interview links (default: `http://localhost:5173`) |
| `DATABASE_URL` | No | SQLite path (default: `sqlite:///./preinterviewai.db`) |
| `JWT_SECRET` | No | Session token secret — **change in production** |
| `SESSION_EXPIRE_HOURS` | No | Session TTL in hours (default: `72`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

**Recommended LLM models for OpenRouter:**

```
LLM_MODEL=google/gemini-2.5-flash          # fast, free tier, recommended
# Fallback chain (automatic):
# meta-llama/llama-3.3-70b-instruct
# meta-llama/llama-3.1-8b-instruct:free
# deepseek/deepseek-chat
```

> **Note:** `deepseek/deepseek-r1:free` returns HTTP 404 on OpenRouter — do not use it.

**Verifying SMTP:**

```python
# In backend/ with venv active:
python -c "
import sys; sys.path.append('.')
from services.email_service import send_test_email
print(send_test_email('you@yourdomain.com'))
# True = working, False = credentials missing
"
```

---

## Interview state machine

Sessions transition through four states:

```
waiting  →  active  →  completed  →  evaluated
   ↑                        ↑
created by                  set when all questions
schedule/join               answered or session.complete
                            called
```

State is tracked in the `sessions` table via the `status` column. The `current_question_index` field tracks which question the candidate is on. The `answers[]` array stores all transcripts in order.

The `asyncio.Lock` in `conversation_service.py` and `evaluation.py` prevents two concurrent HTTP requests for the same session from both processing simultaneously — eliminating the React StrictMode double-call race condition that caused duplicate TTS audio and duplicate evaluation emails.

---

## API reference

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup` | Register a recruiter account |
| `POST` | `/auth/signin` | Sign in, receive session token |
| `GET` | `/auth/me` | Get current recruiter info |
| `POST` | `/auth/signout` | Invalidate session token |

### Question banks

| Method | Path | Description |
|---|---|---|
| `POST` | `/questions/upload` | Upload CSV / JSON / TXT / DOCX bank |
| `GET` | `/questions/banks` | List all uploaded banks |
| `GET` | `/questions/banks/{id}` | Get single bank by ID |

### Interview session lifecycle (state management)

| Method | Path | Description |
|---|---|---|
| `POST` | `/interview/sessions` | Create session (`status: waiting`) |
| `POST` | `/interview/sessions/{id}/start` | Activate session (`status → active`) |
| `GET` | `/interview/sessions/{id}/next` | Get next question + `current_question_index` + `total_questions` |
| `POST` | `/interview/sessions/{id}/answer` | Submit answer transcript, advances `current_question_index` |
| `POST` | `/interview/sessions/{id}/complete` | Mark complete (`status → completed`) |
| `GET` | `/interview/sessions` | List all sessions |
| `GET` | `/interview/sessions/{id}` | Get single session |

### Conversation (speech-to-speech)

| Method | Path | Description |
|---|---|---|
| `POST` | `/interview/sessions/{id}/conversation` | Main interview loop: records answer → returns next question text + base64 TTS audio. Fires background task to pre-cache next+1 TTS. Protected by per-session `asyncio.Lock`. |

**Request body:**
```json
{ "transcript": "candidate's answer text, or null for initial greeting" }
```

**Response:**
```json
{
  "bot_text": "Question 2 of 5: How do you approach...",
  "audio": "<base64 mp3>",
  "done": false,
  "question_index": 1,
  "total_questions": 5
}
```

### Evaluation

| Method | Path | Description |
|---|---|---|
| `POST` | `/evaluation/{session_id}` | Run AI evaluation on completed session, send emails. Idempotent — returns existing report if already evaluated. Protected by per-session lock. |
| `GET` | `/evaluation/{session_id}` | Retrieve existing evaluation report (JSON) |

### Report

| Method | Path | Description |
|---|---|---|
| `GET` | `/report/{session_id}` | Full evaluation as JSON |
| `GET` | `/report/{session_id}/text` | Human-readable plain-text report for download |

### Scheduling

| Method | Path | Description |
|---|---|---|
| `POST` | `/schedule` | Schedule interview — immediate (`is_immediate: true`) or date/time-gated. Sends invite email. |
| `GET` | `/schedule/join/{token}` | Candidate joins via unique token. Validates time window. Returns `session + bank + scheduled` objects. |
| `GET` | `/schedule/list` | List all scheduled interviews (requires auth) |
| `GET` | `/schedule/{id}` | Get single scheduled interview |

### Speech

| Method | Path | Description |
|---|---|---|
| `POST` | `/speech/transcribe` | Transcribe audio blob (WAV / WebM / OGG) via Whisper |
| `POST` | `/speech/tts` | Synthesize text to audio (ElevenLabs primary, OpenAI fallback) |

---

## Question bank formats

### CSV

```csv
question,topic,difficulty,keywords
"Describe a challenging project you led.",Behavioral,medium,"leadership|scope|delivery"
"What is the difference between REST and GraphQL?",API Design,easy,"http|schema|query"
```

Required column: `question` or `text`. Optional: `topic`, `difficulty`, `keywords` (pipe-separated).

### JSON

```json
{
  "name": "Frontend Interview Q3-2025",
  "role": "Senior Frontend Engineer",
  "questions": [
    {
      "text": "How do you approach performance optimization?",
      "topic": "Performance",
      "difficulty": "hard",
      "keywords": "profiling|caching|lazy loading|memoization"
    }
  ]
}
```

Array format also accepted: `[{ "text": "..." }, ...]`

### TXT

Each line is one question. No metadata is parsed.

```
Tell me about yourself and your most recent project.
What is your approach to debugging a production issue?
Where do you see yourself in five years?
```

### DOCX / DOC

Each paragraph becomes one question. Images and complex formatting are ignored; only plain text is extracted.

---

## Speech-to-speech flow

**Text-to-Speech (TTS)**

ElevenLabs is the primary provider (`eleven_turbo_v2`, voice: Bella, `mp3_22050_32` format). OpenAI `tts-1` (voice: alloy) is the automatic fallback. Audio is cached in memory keyed by MD5 of the text string (max 100 entries). When the conversation step returns a question, a background `asyncio.create_task` immediately pre-warms the TTS cache for the next question — so Q2 onwards plays with near-zero delay.

**Audio format:** The frontend decodes audio as `audio/mpeg` (MP3). This was a critical bug fix — the original code used `audio/wav` which caused silent/broken playback in Chrome on Windows since ElevenLabs returns MP3.

**Speech-to-Text (STT)**

Faster-Whisper (`small` model, CPU `float32` or GPU `float16`). The model is pre-loaded at startup via `asyncio.create_task(_prewarm_whisper())` so the first candidate request does not incur the 5–8 second model-load freeze. Audio is converted to WAV 16 kHz mono via ffmpeg before transcription.

**Silence detection**

The `useSTT` hook monitors RMS audio level every animation frame. After 5 seconds of silence below the `SPEECH_RMS_THRESHOLD` (0.012), recording stops automatically and the blob is sent for transcription. Blobs under 300 bytes are discarded as background noise. A `resultSentRef` guard ensures `onResult` fires at most once per recording session.

**Turn latency breakdown:**

| Stage | Phase 1 |
|---|---|
| Greeting (Q1) | ~1.5 s (TTS synthesis + network) |
| Q2 onwards | ~0.2 s (TTS pre-cached) |
| STT transcription | 1–6 s (depends on audio length + CPU) |
| Conversation logic | < 50 ms (no LLM in real-time path) |
| LLM evaluation | 4–10 s (async, runs after interview) |

**Why the LLM is NOT in the real-time path**

Previous versions called the LLM to generate a conversational acknowledgement between each question (2–5 seconds per turn). This was removed entirely. The bot now uses short, randomized connector phrases ("Got it.", "Understood.", "Question 3 of 5: ...") generated in under 5 ms. The LLM is only called once, asynchronously, for the full evaluation after the interview ends.

---

## AI evaluation

Powered by the LLM configured via `LLM_MODEL` and `LLM_API_KEY`.

**Per question:**
- Score 0–100 with scoring rubric (90–100 exceptional, 75–89 good, 55–74 average, 30–54 weak, 0–29 very weak / skipped)
- Rating: `strong` / `good` / `average` / `weak`
- Strengths list, improvements list
- Short candidate feedback (1–2 sentences)
- Detailed 2–3 paragraph analysis
- Keywords detected from `expected_keywords`
- Communication assessment: clarity, confidence, depth, relevance (0–10 each)

**Overall report:**
- Aggregate score and rating
- Recommendation: `Strong Hire` / `Hire` / `Consider` / `No Hire`
- Executive summary (recruiter-grade paragraph)
- Private hiring notes
- Risk flags
- `generated_at` timestamp

**Fallback without API key:** Rule-based word-count scoring — functional but not meaningful. Set `LLM_API_KEY` in `.env` to enable AI evaluation.

**Model fallback chain (automatic):**

```
1. google/gemini-2.5-flash      (primary — fast, free tier)
2. meta-llama/llama-3.3-70b-instruct
3. meta-llama/llama-3.1-8b-instruct:free
4. deepseek/deepseek-chat
→ fallback evaluator (word-count scoring)
```

---

## Fixes applied in v2.1.0

The following bugs were identified and fixed:

**Double TTS / double question audio (critical)**
React StrictMode fires `useEffect` twice on mount, sending two simultaneous `POST /conversation` requests. Both saw `_state_map[session_id]` as uninitialized, both generated the greeting, and both synthesized TTS — causing the question to play twice. Fixed with `asyncio.Lock` per session in `conversation_service.py`.

**Double evaluation email**
Same race condition: two `POST /evaluation` requests both passed the `status != EVALUATED` check before either wrote back. Fixed with a per-session `asyncio.Lock` in `evaluation.py` with a DB-level re-check inside the lock.

**Wrong audio MIME type**
`useSpeech.js` decoded ElevenLabs audio as `data:audio/wav;base64,...`. ElevenLabs returns MP3 (`mp3_22050_32`). Chrome on Windows failed silently. Fixed to `data:audio/mpeg;base64,...`.

**Whisper causing 5–8 s freeze on first request**
Whisper loaded lazily on the first transcription call. Fixed in `main.py` by pre-loading the model in a background `asyncio.create_task` at startup.

**Broken LLM model (`deepseek/deepseek-r1:free`)**
This model slug returns HTTP 404 on OpenRouter. Removed from the default config. New primary: `google/gemini-2.5-flash`.

**LLM in real-time path (4–8 s per turn)**
LLM was called synchronously between each question to generate an acknowledgement, adding 2–5 s before TTS synthesis. LLM removed from the real-time path entirely. Turn latency drops to ~1 s (TTS only).

**Recommendation field showing full sentences in email subject**
LLaMA sometimes returned `"The candidate requires significant improvement..."` instead of `"No Hire"`. Added `_normalize_recommendation()` in `evaluation.py` to clamp to the four standard values.

**TTS pre-caching not surviving server restart**
In-memory TTS cache lost on restart. Phase 2 migration: replace with Redis-backed cache.

---

## Extending

| Goal | Where to change |
|---|---|
| Change LLM model | `config.py` → `LLM_MODEL` env var |
| Add question topics / difficulties | `models/schemas.py` `Question` model + CSV parser |
| Change voice (ElevenLabs) | `speech_service.py` → `voice_id` constant |
| Add follow-up questions | `conversation_service.py` → add follow-up queue to `handle_node` |
| Swap SQLite for Postgres | `config.py` → `DATABASE_URL=postgresql+asyncpg://...` + swap `sqlite_store.py` |
| Add resume parsing (Phase 2) | New service `resume_service.py` using `pdfminer.six` + LLM extraction |
| Add AI question generation (Phase 2) | New endpoint `POST /questions/generate` using resume + JD as LLM context |
| Multi-tenancy (Phase 2) | Add `org_id` FK to every table, middleware to inject from JWT |
| Add WebRTC / LiveKit (Phase 3) | Replace HTTP speech pipeline with LiveKit room + PipeCAT pipeline per session |
| Deployment | Dockerize backend; Vercel or Cloudflare Pages for frontend; use Postgres in production |

---

## Deployment notes

**Backend (Docker):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend:**
```bash
npm run build          # outputs to frontend/dist/
# Deploy dist/ to Vercel, Cloudflare Pages, or serve via nginx
```

**Production checklist:**
- Set `JWT_SECRET` to a long random string (at least 32 chars)
- Set `DATABASE_URL` to a Postgres connection string (not SQLite)
- Set `APP_BASE_URL` to your production frontend URL (used in invite email links)
- Set `CORS_ORIGINS` to your production frontend domain only
- Configure SMTP credentials for invite / report / thank-you emails
- ffmpeg must be installed on the server for audio conversion (`apt-get install ffmpeg`)
- For GPU-accelerated Whisper, set `TORCH_DEVICE=cuda` and use a GPU instance
