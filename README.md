# Faceless Video Generator

Generate MP4 videos from MP3 voice-overs — with real transcription and burned-in subtitles.

## Architecture

```
┌──────────────────┐       ┌────────────────────┐
│   React + Vite   │──────▶│   FastAPI Backend   │
│   (port 5173)    │ proxy │   (port 8000)       │
└──────────────────┘       └────────┬───────────┘
                                    │
                           ┌────────▼───────────┐
                           │  Background Worker  │
                           │                     │
                           │  1. Whisper (STT)   │
                           │  2. FFmpeg (video)  │
                           │  3. Burn subtitles  │
                           └────────┬───────────┘
                                    │
                           ┌────────▼───────────┐
                           │  SQLite + Local FS  │
                           └────────────────────┘
```

## Features

- **Drag & drop** audio upload (MP3, WAV, M4A, OGG, FLAC, AAC)
- **Real-time job tracking** with progress bar and pipeline logs
- **Local Whisper transcription** — no API keys needed
- **Word-level SRT subtitles** burned into video
- **Audio-reactive waveform** video background
- **Fallback mode** — static subtitles if transcription fails
- **SQLite persistence** — jobs survive server restarts

## Prerequisites

### 1. Python 3.10+

Download from https://www.python.org/downloads/

### 2. Node.js 18+

Download from https://nodejs.org/

### 3. FFmpeg (required)

**Windows (recommended — using winget):**
```powershell
winget install Gyan.FFmpeg
```

**Windows (alternative — using Chocolatey):**
```powershell
choco install ffmpeg
```

**Windows (manual):**
1. Download from https://www.gyan.dev/ffmpeg/builds/
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system PATH

**Verify installation:**
```bash
ffmpeg -version
```

## Quick Start

### 1. Backend Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Frontend Setup

```powershell
cd frontend
npm install
```

### 3. Run (two terminals)

**Terminal 1 — Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```powershell
cd frontend
npm run dev
```

### 4. Open

Navigate to **http://localhost:5173**

## Usage

1. Upload an MP3 file (max 50 MB, 2 minutes)
2. Click **Generate Video**
3. Watch the pipeline progress in real time
4. Download the final MP4 when complete

## Configuration

Edit `backend/config.py`:

| Setting              | Default | Description                             |
| -------------------- | ------- | --------------------------------------- |
| `WHISPER_MODEL`      | `base`  | Whisper model size (tiny/base/small)    |
| `VIDEO_WIDTH`        | `1280`  | Output video width                      |
| `VIDEO_HEIGHT`       | `720`   | Output video height                     |
| `MAX_AUDIO_DURATION` | `120`   | Max audio length in seconds             |
| `FONT_SIZE`          | `28`    | Subtitle font size                      |

You can also set the Whisper model via environment variable:
```bash
set WHISPER_MODEL=small
```

## API Endpoints

| Method | Path                        | Description               |
| ------ | --------------------------- | ------------------------- |
| POST   | `/api/jobs/upload`          | Upload audio, create job  |
| GET    | `/api/jobs/{id}`            | Get job status            |
| GET    | `/api/jobs/{id}/download`   | Download generated MP4    |
| GET    | `/api/jobs/`                | List all jobs             |
| GET    | `/api/health`               | Health check              |

## Tech Stack

- **Frontend:** React 18 + Vite
- **Backend:** Python FastAPI + Uvicorn
- **Transcription:** OpenAI Whisper (local)
- **Video:** FFmpeg (H.264 + AAC)
- **Database:** SQLite (WAL mode)
- **Worker:** Background thread (daemon)
