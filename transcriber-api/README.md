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
- `POST /api/media-transcriber/jobs/{job_id}/publish/feishu` - Publish job content to Feishu document
- `GET /health` - Health check

## Publish to Feishu

Configure Feishu credentials via environment variables:

```bash
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
```

**API Example:**

```bash
curl -X POST http://localhost:3002/api/media-transcriber/jobs/{job_id}/publish/feishu
```

**Success Response:**

```json
{
  "job_id": "job_abc123",
  "status": "success",
  "document_id": "doc_xyz",
  "document_url": "https://feishu.cn/docx/doc_xyz"
}
```

**Error Response (no distilled content):**

```json
{
  "job_id": "job_abc123",
  "status": "error",
  "error_message": "Job has no distilled content"
}
```

Note: Jobs must be completed with `distilled_content` before publishing.