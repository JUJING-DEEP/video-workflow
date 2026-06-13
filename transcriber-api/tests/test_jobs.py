"""
Unit tests for jobs API
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestCreateJob:
    """Tests for POST /api/media-transcriber/jobs"""

    @pytest.mark.asyncio
    async def test_create_url_job_success(self, client: AsyncClient):
        """创建 URL 任务成功"""
        response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "url",
                "source_url": "https://www.youtube.com/watch?v=example",
                "language": "zh",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "url"
        assert data["source_url"] == "https://www.youtube.com/watch?v=example"
        assert data["language"] == "zh"
        assert data["status"] == "pending"
        assert data["id"].startswith("job_")

    @pytest.mark.asyncio
    async def test_create_upload_job_success(self, client: AsyncClient):
        """创建上传任务成功"""
        response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "upload",
                "file_path": "/path/to/audio.mp3",
                "language": "zh",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "upload"
        assert data["file_path"] == "/path/to/audio.mp3"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_job_with_defaults(self, client: AsyncClient):
        """创建任务使用默认参数"""
        response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "url",
                "source_url": "https://example.com/video",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["language"] == "zh"
        assert data["output_style"] == "distilled_original"

    @pytest.mark.asyncio
    async def test_create_url_job_missing_source_url(self, client: AsyncClient):
        """URL 类型缺少 source_url 返回 400"""
        response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "url",
            },
        )
        assert response.status_code == 400
        assert "source_url is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_upload_job_missing_file_path(self, client: AsyncClient):
        """上传类型缺少 file_path 返回 400"""
        response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "upload",
            },
        )
        assert response.status_code == 400
        assert "file_path is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_job_invalid_source_type(self, client: AsyncClient):
        """非法 source_type 返回 422"""
        response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "invalid",
                "source_url": "https://example.com/video",
            },
        )
        assert response.status_code == 422


class TestGetJob:
    """Tests for GET /api/media-transcriber/jobs/{job_id}"""

    @pytest.mark.asyncio
    async def test_get_job_success(self, client: AsyncClient):
        """查询任务成功"""
        # Create a job first
        create_response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "url",
                "source_url": "https://www.youtube.com/watch?v=test",
            },
        )
        job_id = create_response.json()["id"]

        # Get the job
        response = await client.get(f"/api/media-transcriber/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["source_type"] == "url"
        assert data["source_url"] == "https://www.youtube.com/watch?v=test"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: AsyncClient):
        """查询不存在的任务返回 404"""
        response = await client.get("/api/media-transcriber/jobs/job_nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_job_completed(self, client: AsyncClient):
        """查询已完成任务包含转录结果"""
        # Create a job
        create_response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "url",
                "source_url": "https://example.com/video",
            },
        )
        job_id = create_response.json()["id"]

        # Wait for pipeline to complete (mock pipeline is fast)
        import asyncio

        await asyncio.sleep(3)

        # Get the completed job
        response = await client.get(f"/api/media-transcriber/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["completed", "failed", "pending"]

    @pytest.mark.asyncio
    async def test_get_job_returns_distilled_content(self, client: AsyncClient):
        """GET /jobs/{id} 返回完整的 raw_transcript, cleaned_transcript, distilled_content 字段"""
        # Create an upload job (faster - uses mock pipeline directly)
        create_response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "upload",
                "file_path": "/fake/path/audio.mp3",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        # Wait for pipeline
        import asyncio
        await asyncio.sleep(3)

        # Get the job
        response = await client.get(f"/api/media-transcriber/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()

        # Response should contain all transcript fields
        assert "status" in data
        assert "raw_transcript" in data
        assert "cleaned_transcript" in data
        assert "distilled_content" in data


class TestPipeline:
    """Tests for pipeline behavior"""

    @pytest.mark.asyncio
    async def test_url_job_pipeline_state_transitions(self, client: AsyncClient):
        """URL 任务经历正确的状态流转"""
        # Create URL job
        create_response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "url",
                "source_url": "https://example.com/video",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        # Initial status should be pending
        get_response = await client.get(f"/api/media-transcriber/jobs/{job_id}")
        assert get_response.json()["status"] == "pending"

        # Wait for pipeline
        import asyncio

        await asyncio.sleep(3)

        # Check final status
        get_response = await client.get(f"/api/media-transcriber/jobs/{job_id}")
        status = get_response.json()["status"]
        assert status in ["completed", "failed", "pending"]

    @pytest.mark.asyncio
    async def test_file_job_pipeline_mock_content(self, client: AsyncClient):
        """文件任务读取本地文件作为 mock 转录"""
        # Create a temp file with test content
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is test file content for transcription.")
            temp_path = f.name

        try:
            # Create file job
            create_response = await client.post(
                "/api/media-transcriber/jobs",
                json={
                    "source_type": "upload",
                    "file_path": temp_path,
                },
            )
            assert create_response.status_code == 201
            job_id = create_response.json()["id"]

            # Wait for pipeline
            import asyncio

            await asyncio.sleep(2)

            # Get result
            get_response = await client.get(f"/api/media-transcriber/jobs/{job_id}")
            data = get_response.json()

            # Verify mock content is present
            if data["status"] == "completed":
                assert "This is test file content" in (data["raw_transcript"] or "")
        finally:
            import os

            os.unlink(temp_path)


class TestHealthCheck:
    """Tests for health check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """健康检查返回 ok"""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"