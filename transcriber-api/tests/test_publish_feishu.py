"""Tests for Feishu publish endpoint"""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ["FEISHU_APP_ID"] = "test_app_id"
os.environ["FEISHU_APP_SECRET"] = "test_secret"


@pytest.mark.asyncio
async def test_publish_success(client, db):
    """Test successful publish to Feishu"""
    from httpx import AsyncClient
    from app.db.database import JobModel
    from datetime import datetime

    # Create a completed job directly in DB with distilled content
    job_id = "test_job_publish_ok"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Test Transcript\n\nThis is the distilled content.",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.document_id = "doc_abc123"
        mock_result.document_url = "https://feishu.cn/docx/doc_abc123"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "success"
        assert data["document_id"] == "doc_abc123"
        assert "feishu.cn" in (data["document_url"] or "")


@pytest.mark.asyncio
async def test_job_not_found(client):
    """Test 404 when job doesn't exist"""
    response = await client.post(
        "/api/media-transcriber/jobs/nonexistent_job/publish/feishu"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_no_distilled_content(client, db):
    """Test error when job has no distilled_content"""
    from app.db.database import JobModel
    from datetime import datetime

    # Create a job with no distilled_content
    job_id = "test_job_no_content"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": None,  # No content!
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    response = await client.post(
        f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "no distilled content" in data["error_message"].lower()


@pytest.mark.asyncio
async def test_feishu_api_failure(client, db):
    """Test error when Feishu API fails"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_job_fail"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "API rate limit exceeded"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "rate limit" in data["error_message"].lower()


@pytest.mark.asyncio
async def test_token_not_in_error_message(client, db):
    """Test that tokens/secrets don't appear in error messages"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_job_sanitize"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "Auth failed: invalid token abc123secretdef456"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        if data["error_message"]:
            assert "abc123secretdef456" not in data["error_message"]


@pytest.mark.asyncio
async def test_sanitizes_app_secret(client, db):
    """Test that app_secret values are sanitized"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_sanitize_secret"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "app_secret=abc123secretdef456 failed"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        if data["error_message"]:
            assert "abc123secretdef456" not in data["error_message"]
            assert "[REDACTED]" in data["error_message"]


@pytest.mark.asyncio
async def test_sanitizes_bearer_token(client, db):
    """Test that Bearer token values are sanitized"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_sanitize_bearer"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "token: abc123secretdef456 is invalid"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        if data["error_message"]:
            assert "abc123secretdef456" not in data["error_message"]


@pytest.mark.asyncio
async def test_sanitizes_password(client, db):
    """Test that password values are sanitized"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_sanitize_password"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "password=abc123 is wrong"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        if data["error_message"]:
            assert "abc123" not in data["error_message"]


@pytest.mark.asyncio
async def test_sanitizes_tenant_access_token(client, db):
    """Test that tenant_access_token values are sanitized"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_sanitize_tenant"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "tenant_access_token=abc123secretdef456abc123 expired"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        if data["error_message"]:
            assert "abc123secretdef456abc123" not in data["error_message"]


@pytest.mark.asyncio
async def test_normal_error_not_harmed(client, db):
    """Test that normal error messages are preserved"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_normal_error"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "Invalid document title"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Invalid document title" in data["error_message"]


@pytest.mark.asyncio
async def test_missing_feishu_config(client, db):
    """Test error when FEISHU credentials are not configured"""
    from app.db.database import JobModel
    from datetime import datetime

    job_id = "test_job_no_config"
    await db.create_job({
        "id": job_id,
        "source_type": "url",
        "source_url": "https://example.com/video",
        "language": "zh",
        "output_style": "distilled_original",
        "status": "completed",
        "distilled_content": "# Content",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    with patch.dict(os.environ, {"FEISHU_APP_ID": "", "FEISHU_APP_SECRET": ""}):
        response = await client.post(
            f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "configure" in data["error_message"].lower()