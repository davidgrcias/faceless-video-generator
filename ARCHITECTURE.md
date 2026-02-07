# Faceless Video Generator — Technical Overview

## 1. Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│                                                                 │
│   ┌───────────────────────────────────────────────────────┐     │
│   │              React SPA (Vite, port 5173)              │     │
│   │                                                       │     │
│   │  FileUpload ──▶ GenerateButton ──▶ JobStatus/Download │     │
│   │                                                       │     │
│   │  useJob hook: upload() → poll every 1.5s → done       │     │
│   └──────────────────────┬────────────────────────────────┘     │
└──────────────────────────┼──────────────────────────────────────┘
                           │  HTTP (proxied by Vite → :8000)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                    │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ POST /upload │  │ GET /{id}    │  │ GET /{id}/download     │ │
│  │              │  │              │  │                        │ │
│  │ • Validate   │  │ • Return job │  │ • Serve MP4 file       │ │
│  │   file type  │  │   status,    │  │   with FileResponse    │ │
│  │ • Check size │  │   progress,  │  │                        │ │
│  │ • ffprobe    │  │   logs       │  │                        │ │
│  │   duration   │  │              │  │                        │ │
│  │ • Save disk  │  │              │  │                        │ │
│  │ • Create job │  │              │  │                        │ │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────┘ │
│         │                 │                        │             │
│         ▼                 ▼                        ▼             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  SQLite (WAL mode)                         │  │
│  │                                                            │  │
│  │  jobs: id | status | progress | audio_path | output_path   │  │
│  │         | srt_path | logs | error | created_at | updated_at│  │
│  └────────────────────────────┬───────────────────────────────┘  │
│                               │                                  │
│  ┌────────────────────────────▼───────────────────────────────┐  │
│  │              Background Worker (daemon thread)             │  │
│  │                                                            │  │
│  │  Poll loop (every 2s):                                     │  │
│  │    next_queued_job() → run_pipeline() → update status      │  │
│  │                                                            │  │
│  │  Pipeline Steps:                                           │  │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │  │
│  │  │ ffprobe │─▶│ Whisper  │─▶│ FFmpeg   │─▶│ FFmpeg     │  │  │
│  │  │ duration│  │ STT→SRT  │  │ waveform │  │ burn subs  │  │  │
│  │  │  (5%)   │  │ (15-50%) │  │ (50-70%) │  │ (70-100%)  │  │  │
│  │  └─────────┘  └──────────┘  └──────────┘  └────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Local Filesystem:                                               │
│  storage/uploads/   ← uploaded MP3 files                         │
│  storage/outputs/   ← generated MP4 + SRT files                  │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Tech | Role |
|-----------|------|------|
| **Frontend** | React 18 + Vite | Upload UI, real-time polling, download |
| **API Layer** | FastAPI + Uvicorn | REST endpoints, input validation, file serving |
| **Job Store** | SQLite (WAL) | Persistent job state, progress, logs |
| **Worker** | Python `threading.Thread` | Sequential job processor, polls SQLite |
| **Transcriber** | OpenAI Whisper (local) | Audio → word-level SRT subtitles |
| **Video Builder** | FFmpeg (subprocess) | Waveform generation, subtitle burn-in, MP4 encoding |

### Request Flow

```
1. User drops MP3 → frontend sends POST /api/jobs/upload
2. Backend validates (type, size, duration via ffprobe), saves file, creates job row → returns job_id
3. Frontend begins polling GET /api/jobs/{id} every 1.5 seconds
4. Worker thread picks up queued job, marks it "processing"
5. Pipeline runs: Whisper transcribes → FFmpeg builds waveform → FFmpeg burns subtitles
6. Each step updates progress (5% → 50% → 70% → 90% → 100%) and appends logs
7. On completion: status="done", output_path set → frontend shows download link
8. On failure: status="failed", error message set → frontend shows error
```

### Key Design Decisions

- **Polling over WebSocket:** Simpler to implement and debug. 1.5s interval is responsive enough for a job that takes 30-90 seconds. No connection state management needed.
- **SQLite over in-memory:** Jobs survive server restarts. WAL mode allows concurrent reads during writes. Single-file, zero-config.
- **Thread over Celery:** Single daemon thread is sufficient for MVP with max 60s audio. No Redis/broker dependency. Easy to reason about.
- **Whisper local over API:** No API key required, works fully offline, deterministic results. Model is cached after first load.
- **Graceful fallback:** If Whisper fails (bad audio, OOM), pipeline falls back to static subtitle text. The demo never breaks.

---

## 2. Bottlenecks

### Performance Bottlenecks

| Bottleneck | Impact | Where | Measured |
|------------|--------|-------|----------|
| **Whisper model cold start** | ~5-10s first-time load for `base` model | `transcriber.py:_get_model()` | One-time per server lifecycle |
| **Whisper transcription** | ~3-8s for 30s audio (CPU-only) | `transcriber.py:transcribe()` | Proportional to audio length |
| **FFmpeg waveform render** | ~2-5s for 30s video at 720p/30fps | `video_builder.py:generate_waveform_video()` | Proportional to duration × resolution |
| **FFmpeg subtitle burn-in** | ~3-8s (re-encodes full video) | `video_builder.py:build_final_video()` | Proportional to duration × resolution |
| **Single worker thread** | Jobs queue up sequentially | `processor.py:VideoWorker` | 5 concurrent uploads = 5× wait time |

### Scalability Bottlenecks

| Bottleneck | Impact | Threshold |
|------------|--------|-----------|
| **No file cleanup** | Disk fills over time | ~100 jobs = ~1-2 GB at 720p |
| **SQLite single-writer** | Write contention under load | Not an issue for < 50 concurrent users |
| **Upload reads full file into memory** | 50MB max → 50MB RAM spike per upload | Server with < 512MB RAM |
| **Polling interval** | 1.5s × N active clients = N requests/1.5s | Not an issue for < 50 active clients |
| **No request queue limits** | Unbounded job queue | Users could enqueue hundreds of jobs |

### The Real Constraint in Practice

For the use case (30-60s audio, single user, local environment), the **dominant bottleneck is Whisper transcription on CPU**. On a typical machine without GPU:

```
30s audio ≈ 5-8s transcription (base model)
30s audio ≈ 15-25s transcription (small model, more accurate)
```

FFmpeg encoding is fast by comparison. Total pipeline time for a 30s clip:

```
Duration check:     ~0.1s
Whisper (base):     ~5-8s
Waveform render:    ~2-4s
Subtitle burn-in:   ~3-5s
─────────────────────────
Total:              ~10-18s
```

---

## 3. What I Would Improve for Production

### Priority 1 — Reliability & Operations

| Improvement | Why | How |
|-------------|-----|-----|
| **File cleanup with TTL** | Prevent disk exhaustion | Background task that deletes files older than 24h; add `expires_at` column to jobs table |
| **Docker + docker-compose** | Reproducible environment, includes FFmpeg | `Dockerfile` with Python + FFmpeg + Whisper model pre-downloaded; `docker-compose.yml` with one command to run |
| **Health check with dependency status** | Know if FFmpeg/Whisper are available before users hit errors | `/api/health` returns `{ffmpeg: true, whisper_model: "base", disk_free: "12GB"}` |
| **Structured logging (JSON)** | Parseable by log aggregators (ELK, Datadog) | Replace `logging.basicConfig` with `structlog` or JSON formatter |

### Priority 2 — Scalability

| Improvement | Why | How |
|-------------|-----|-----|
| **Redis + Celery task queue** | Multiple workers, retry logic, rate limiting, priority queues | Replace `VideoWorker` thread with Celery workers consuming from Redis broker |
| **S3/R2 for file storage** | Scalable, durable, serve downloads via CDN | Upload to S3 after receiving, presigned URLs for download, remove local filesystem dependency |
| **WebSocket for real-time updates** | Eliminate polling overhead, instant progress updates | FastAPI WebSocket endpoint; worker pushes status changes via Redis pub/sub |
| **GPU-accelerated Whisper** | 10-50× faster transcription | `whisper` with CUDA, or switch to `faster-whisper` (CTranslate2 backend) |

### Priority 3 — User Experience

| Improvement | Why | How |
|-------------|-----|-----|
| **Cancel job** | User uploaded wrong file | Add `DELETE /api/jobs/{id}` endpoint; worker checks cancellation flag between pipeline steps |
| **Job history page** | See past generations | Already have `GET /api/jobs/` endpoint; add a history panel in the frontend |
| **Multiple background styles** | Visual variety | Image-per-scene system: split audio into N segments, generate/select background per segment |
| **Custom subtitle styling** | User control over font, position, color | Pass style options in upload request; apply in FFmpeg subtitle filter |

### Priority 4 — Security & Hardening

| Improvement | Why | How |
|-------------|-----|-----|
| **Rate limiting** | Prevent abuse | `slowapi` middleware on upload endpoint (e.g., 10 uploads/min per IP) |
| **Input sanitization** | Malicious filenames, path traversal | Already using UUID-based filenames; add MIME type validation with `python-magic` |
| **Max queue depth** | Prevent resource exhaustion | Reject uploads when queue has > N pending jobs |
| **Authentication** | Multi-user support | JWT tokens or session-based auth; associate jobs with users |

### If I Had 2 More Hours

The highest-impact changes I'd make next, in order:

1. **`faster-whisper`** — Drop-in replacement, 4× faster on CPU, lower memory. ~30 min.
2. **File cleanup cron** — Background task deleting files older than 1 hour. ~20 min.
3. **Docker setup** — Single `docker-compose up` to run everything. ~30 min.
4. **WebSocket progress** — Real-time updates without polling. ~40 min.
