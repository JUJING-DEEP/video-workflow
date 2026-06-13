# Video Workflow

A media transcription and organization Agent that converts audio/video content into shareable, distilled transcripts.

## Project Overview

Video Workflow accepts URLs or local files, downloads media, extracts audio, transcribes speech to text, and cleans the transcript for readability. Currently in active development.

## Architecture

```
                                    ┌──────────────────┐
                                    │      User        │
                                    └────────┬─────────┘
                                             │ input (URL / file)
                                             ▼
                              ┌──────────────────────────┐
                              │   FastAPI Server         │
                              │   POST /api/tasks        │
                              └────────────┬─────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    ▼                      ▼                      ▼
            ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
            │ MediaDownload│     │ AudioExtract  │     │  Pipeline     │
            │   (yt-dlp)   │────▶│   (ffmpeg)    │────▶│  (orchestrate)│
            └───────────────┘     └───────────────┘     └───────┬───────┘
                                                               │
                              ┌────────────────────────────────┼────────────┐
                              ▼                                ▼            ▼
                    ┌───────────────┐               ┌───────────────┐ ┌───────────────┐
                    │ Transcription │               │   Cleaner     │ │  Distiller    │
                    │ (faster-whisper)             │ (Transcript)  │ │   (future)    │
                    └───────────────┘               └───────────────┘ └───────────────┘
```

## Current Features

### Implemented
- [x] **URL / File Input** — Accept YouTube, B站, 小宇宙, or local files
- [x] **Media Download** — yt-dlp for publicly accessible media
- [x] **Audio Extraction** — ffmpeg conversion to WAV (16kHz mono)
- [x] **ASR Transcription** — faster-whisper with mock fallback
- [x] **Transcript Cleaning** — Remove timestamps, speaker labels, ASR noise, verbal fillers
- [x] **Async Pipeline** — Background job processing with state tracking
- [x] **Mock Mode** — Falls back to mock pipeline when real services unavailable

### In Progress
- [ ] **Distillation** — LLM-powered shareable transcript generation
- [ ] **Feishu Integration** — Publish to Feishu documents
- [ ] **Frontend Dashboard** — Next.js web interface
- [ ] **Docker Deployment** — Containerized deployment

## Local Development

### Prerequisites
- Python 3.11+
- yt-dlp (`brew install yt-dlp`)
- ffmpeg (`brew install ffmpeg`)
- faster-whisper model (downloaded on first use)

### Setup

```bash
# Enter API directory
cd transcriber-api

# Create virtual environment
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt

# Set environment variables
export DATABASE_URL="sqlite+aiosqlite:///./transcriber.db"
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
```

### Run API Server

```bash
cd transcriber-api
.venv/bin/uvicorn app.main:app --reload --port 3002
```

### Run Worker (background pipeline)

```bash
cd transcriber-api
.venv/bin/python -m app.services.pipeline
```

## Running Tests

```bash
cd transcriber-api
.venv/bin/python -m pytest tests/ -v
```

Test output:
```
======================== 36 passed, 1 warning in 20.43s ========================
```

## API Examples

### Create a transcription job

```bash
curl -X POST http://localhost:3002/api/media-transcriber/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "url",
    "source_url": "https://www.youtube.com/watch?v=example",
    "language": "zh"
  }'
```

Response:
```json
{
  "id": "job_abc123def456",
  "source_type": "url",
  "source_url": "https://www.youtube.com/watch?v=example",
  "status": "pending",
  "language": "zh",
  "created_at": "2026-06-14T00:00:00Z"
}
```

### Query job status

```bash
curl http://localhost:3002/api/media-transcriber/jobs/job_abc123def456
```

Response:
```json
{
  "id": "job_abc123def456",
  "status": "completed",
  "raw_transcript": "...",
  "cleaned_transcript": "...",
  "distilled_content": "# 转录稿\n\n...",
  "document_url": null
}
```

### Health check

```bash
curl http://localhost:3002/health
```

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 1 | Task API + SQLite | ✅ Completed |
| Phase 2 | Real media processing pipeline | ✅ Completed |
| Phase 3 | Frontend dashboard | 🔄 In Progress |
| Phase 3 | Distillation engine (LLM) | 📋 Planned |
| Phase 4 | Feishu document publishing | 📋 Planned |
| Phase 5 | Docker deployment | 📋 Planned |

## Security Principles

1. **No credential storage** — Tokens, cookies, and secrets are never written to code, logs, or database
2. **Environment-only secrets** — All credentials come from environment variables
3. **Error message sanitization** — Error messages are scrubbed of sensitive data before logging
4. **No bypass of access controls** — The system never circumvents login walls, paywalls, DRM, or private content restrictions
5. **Temporary file cleanup** — Media files are deleted immediately after processing

## Data Flow

```
URL/File Input
    │
    ▼
SourceResolver ──▶ Identify platform capabilities
    │
    ▼
MediaDownloader ──▶ yt-dlp download (or mock)
    │
    ▼
AudioExtractor ──▶ ffmpeg WAV conversion
    │
    ▼
Transcriber ──▶ faster-whisper ASR
    │
    ▼
Cleaner ──▶ Remove timestamps, noise, fillers
    │
    ▼
Distiller ──▶ (future) LLM structured output
    │
    ▼
FeishuDoc ──▶ (future) Create & share document
```

## Directory Structure

```
video-workflow/
├── transcriber-api/           # FastAPI transcription service
│   ├── app/
│   │   ├── db/               # SQLite/SQLAlchemy
│   │   ├── models/           # Pydantic models
│   │   ├── routes/           # API endpoints
│   │   └── services/         # Core business logic
│   │       ├── media_downloader.py   # yt-dlp
│   │       ├── audio_extractor.py    # ffmpeg
│   │       ├── transcriber.py        # faster-whisper
│   │       ├── cleaner.py            # text cleaning
│   │       └── pipeline.py           # orchestration
│   └── tests/                # 36 unit tests
├── client/                   # (legacy) React video pipeline
├── server/                   # (legacy) Express API
└── src/agents/               # (legacy) Python agents
```

## License

Private project — All rights reserved