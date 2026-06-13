# Media Transcription API

FastAPI-based transcription service for Phase 1 MVP.

## Quick Start

```bash
# Install dependencies
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt

# Run tests
.venv/bin/python -m pytest tests/ -v

# Start server
.venv/bin/uvicorn app.main:app --reload --port 3002
```

## API Endpoints

- `POST /api/media-transcriber/jobs` - Create transcription job
- `GET /api/media-transcriber/jobs/{job_id}` - Get job status
- `GET /health` - Health check