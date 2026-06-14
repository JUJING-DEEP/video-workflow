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


@pytest.mark.asyncio
async def test_health_check_success(client):
    """Test Feishu health check returns healthy when credentials are valid"""
    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_publisher = MagicMock()
        mock_publisher.health_check.return_value = {"status": "healthy"}
        mock_publisher_cls.return_value = mock_publisher

        response = await client.get("/api/media-transcriber/health/feishu")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_auth_failure(client):
    """Test Feishu health check returns unhealthy when token fetch fails"""
    with patch("app.routes.jobs.FeishuPublisher") as mock_publisher_cls:
        mock_publisher = MagicMock()
        mock_publisher.health_check.return_value = {
            "status": "unhealthy",
            "reason": "invalid credentials"
        }
        mock_publisher_cls.return_value = mock_publisher

        response = await client.get("/api/media-transcriber/health/feishu")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "invalid credentials" in data.get("reason", "")


@pytest.mark.asyncio
async def test_health_check_missing_config(client):
    """Test Feishu health check returns unhealthy when credentials not configured"""
    with patch.dict(os.environ, {"FEISHU_APP_ID": "", "FEISHU_APP_SECRET": ""}):
        response = await client.get("/api/media-transcriber/health/feishu")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "configure" in data["reason"].lower()


@pytest.mark.asyncio
async def test_folder_token_enabled(client, db):
    """Test publish works when folder_token is configured"""
    from datetime import datetime

    job_id = "test_folder_enabled"
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
        mock_result.success = True
        mock_result.document_id = "doc_folder_test"
        mock_result.document_url = "https://feishu.cn/docx/doc_folder_test"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        with patch.dict(os.environ, {
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret_test",
            "FEISHU_FOLDER_TOKEN": "folder_token_abc123secretdef456",
        }):
            response = await client.post(
                f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


@pytest.mark.asyncio
async def test_folder_token_disabled(client, db):
    """Test publish works when folder_token is NOT configured (backward compat)"""
    from datetime import datetime

    job_id = "test_folder_disabled"
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
        mock_result.success = True
        mock_result.document_id = "doc_no_folder"
        mock_result.document_url = "https://feishu.cn/docx/doc_no_folder"
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = mock_result
        mock_publisher_cls.return_value = mock_publisher

        with patch.dict(os.environ, {
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret_test",
            "FEISHU_FOLDER_TOKEN": "",
        }):
            response = await client.post(
                f"/api/media-transcriber/jobs/{job_id}/publish/feishu"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


@pytest.mark.asyncio
async def test_folder_token_not_leaked_in_error(client, db):
    """Test that folder_token does not appear in error messages"""
    from datetime import datetime

    job_id = "test_folder_sanitize"
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
        mock_result.error_message = "folder_token=abc123secretdef456abc123 is invalid"
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
async def test_feishu_publisher_sanitize_folder_token():
    """Test FeishuPublisher._sanitize_error catches folder_token"""
    from app.services.feishu_publisher import FeishuPublisher, FeishuConfig

    config = FeishuConfig(app_id="cli_test", app_secret="secret_test")
    publisher = FeishuPublisher(config)

    # folder_token pattern - value should be redacted
    msg = "folder_token=abc123secretdef456abc123 is invalid"
    sanitized = publisher._sanitize_error(msg)
    assert "abc123secretdef456abc123" not in sanitized
    assert "[REDACTED]" in sanitized


@pytest.mark.asyncio
async def test_feishu_publisher_sanitize_bearer_token():
    """Test FeishuPublisher._sanitize_error catches bearer token"""
    from app.services.feishu_publisher import FeishuPublisher, FeishuConfig

    config = FeishuConfig(app_id="cli_test", app_secret="secret_test")
    publisher = FeishuPublisher(config)

    msg = "Bearer abc123secretdef456abc123 is invalid"
    sanitized = publisher._sanitize_error(msg)
    assert "abc123secretdef456abc123" not in sanitized


@pytest.mark.asyncio
async def test_feishu_publisher_health_check_no_app_id():
    """Test health_check returns unhealthy when app_id is empty"""
    from app.services.feishu_publisher import FeishuPublisher, FeishuConfig

    config = FeishuConfig(app_id="", app_secret="secret_test")
    publisher = FeishuPublisher(config)
    result = publisher.health_check()
    assert result["status"] == "unhealthy"
    assert "app_id" in result["reason"].lower()


@pytest.mark.asyncio
async def test_feishu_publisher_health_check_no_app_secret():
    """Test health_check returns unhealthy when app_secret is empty"""
    from app.services.feishu_publisher import FeishuPublisher, FeishuConfig

    config = FeishuConfig(app_id="cli_test", app_secret="")
    publisher = FeishuPublisher(config)
    result = publisher.health_check()
    assert result["status"] == "unhealthy"
    assert "app_secret" in result["reason"].lower()


@pytest.mark.asyncio
async def test_feishu_publisher_health_check_token_failure():
    """Test health_check returns unhealthy when token fetch fails"""
    from app.services.feishu_publisher import FeishuPublisher, FeishuConfig, FeishuAuthError
    from unittest.mock import patch

    config = FeishuConfig(app_id="cli_test", app_secret="secret_test")
    publisher = FeishuPublisher(config)

    with patch.object(publisher, "_get_token", side_effect=FeishuAuthError("invalid credentials")):
        result = publisher.health_check()
        assert result["status"] == "unhealthy"
        assert "invalid credentials" in result["reason"]


@pytest.mark.asyncio
async def test_feishu_publisher_health_check_success():
    """Test health_check returns healthy when token fetch succeeds"""
    from app.services.feishu_publisher import FeishuPublisher, FeishuConfig

    config = FeishuConfig(app_id="cli_test", app_secret="secret_test")
    publisher = FeishuPublisher(config)

    with patch.object(publisher, "_get_token", return_value="valid_token_abc123"):
        result = publisher.health_check()
        assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_feishu_config_with_folder_token():
    """Test FeishuConfig accepts folder_token"""
    from app.services.feishu_publisher import FeishuConfig

    config = FeishuConfig(
        app_id="cli_test",
        app_secret="secret_test",
        folder_token="folder_token_abc123"
    )
    assert config.folder_token == "folder_token_abc123"


@pytest.mark.asyncio
async def test_feishu_config_without_folder_token():
    """Test FeishuConfig defaults folder_token to None"""
    from app.services.feishu_publisher import FeishuConfig

    config = FeishuConfig(app_id="cli_test", app_secret="secret_test")
    assert config.folder_token is None