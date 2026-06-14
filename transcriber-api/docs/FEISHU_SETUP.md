# Feishu Integration Setup Guide

This guide walks you through setting up a Feishu (Lark) self-built application for the Media Transcription API.

---

## Step 1: Create a Feishu Self-Built Application

1. Go to the [Feishu Open Platform](https://open.feishu.cn/app) (open.feishu.cn/app)
2. Sign in with your Feishu account
3. Click **Create self-built app**
4. Fill in:
   - **App name**: `Media Transcription API` (or any name you prefer)
   - **App description**: `Transcribes audio/video content and publishes to Feishu documents`
5. Click **Create**

---

## Step 2: Get APP_ID and APP_SECRET

1. In your app's overview page, click **Credentials and Base Info** in the left sidebar
2. Copy your:
   - **App ID** (starts with `cli_`) → use as `FEISHU_APP_ID`
   - **App Secret** → use as `FEISHU_APP_SECRET`

---

## Step 3: Enable Cloud Documents (Docx) Capability

1. In the left sidebar, go to **Permissions Management**
2. Search for and enable the following scopes:

| Scope | Purpose |
|-------|---------|
| `docx:document:create` | Create new documents |
| `docx:block:create` | Write content to documents |

3. Click **Apply** (some scopes may require enterprise admin approval)

---

## Step 4: (Optional) Get folder_token

If your enterprise requires documents to be created in a specific folder:

1. Open Feishu Docs in your browser
2. Navigate to the target folder
3. Right-click the folder → **Copy link**
4. The link will contain a `folder` parameter (base64 encoded)
5. Use that value as `FEISHU_FOLDER_TOKEN`

**Note**: `folder_token` is optional. If not provided, the document is created in the user's personal space.

---

## Step 5: Configure Environment Variables

```bash
# Required
export FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxxx
export FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional - specify a folder for created documents
export FEISHU_FOLDER_TOKEN=xxxxxxxxxxxxxxxxxxxxxx
```

Or add to `transcriber-api/.env`:

```
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_FOLDER_TOKEN=xxxxxxxxxxxxxxxxxxxxxx  # optional
```

---

## Step 6: Verify Integration

### 6.1 Health Check

```bash
curl http://localhost:3002/api/media-transcriber/health/feishu
```

**Healthy response:**
```json
{"status": "healthy"}
```

**Unhealthy response:**
```json
{"status": "unhealthy", "reason": "FEISHU_APP_ID and FEISHU_APP_SECRET must be configured"}
```

### 6.2 End-to-End Test

1. Start the server:
   ```bash
   cd transcriber-api
   .venv/bin/uvicorn app.main:app --reload --port 3002
   ```

2. Create a transcription job:
   ```bash
   curl -X POST http://localhost:3002/api/media-transcriber/jobs \
     -H "Content-Type: application/json" \
     -d '{"source_type": "upload", "file_path": "/path/to/audio.mp3"}'
   ```

3. Wait for the job to complete (check status via `GET /jobs/{job_id}`)

4. Publish to Feishu:
   ```bash
   curl -X POST http://localhost:3002/api/media-transcriber/jobs/{job_id}/publish/feishu
   ```

5. If successful, you receive:
   ```json
   {
     "job_id": "job_abc123",
     "status": "success",
     "document_id": "doc_xyz...",
     "document_url": "https://feishu.cn/docx/doc_xyz..."
   }
   ```

6. Open the `document_url` in your browser to verify the document was created with content.

---

## Common Issues

### "permission denied" or "scope not granted"

- Go to **Permissions Management** in your app
- Ensure `docx:document:create` and `docx:block:create` are enabled
- If scopes require admin approval, contact your enterprise admin

### "invalid app_id/app_secret"

- Double-check that the App ID and App Secret are copied correctly
- Ensure the app has been **published** (not just created)

### "folder_token is required"

- Some enterprise policies require documents to be created in a specific folder
- Omit `FEISHU_FOLDER_TOKEN` to create in the default personal space, or configure it with a valid folder token

### Document created but empty

- Check the `write_content` step in the server logs
- Feishu block API has a limit of ~500 blocks per request; very long transcripts may need batch writing (not yet implemented)

---

## Environment Variables Summary

| Variable | Required | Description |
|----------|---------|-------------|
| `FEISHU_APP_ID` | ✅ | App ID (starts with `cli_`) |
| `FEISHU_APP_SECRET` | ✅ | App Secret |
| `FEISHU_FOLDER_TOKEN` | ❌ | Target folder token (optional) |