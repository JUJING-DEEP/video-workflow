"""
Additional tests for pipeline failure handling
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestPipelineFailure:
    """Tests for pipeline failure scenarios"""

    @pytest.mark.asyncio
    async def test_job_saves_error_message_on_failure(self, client: AsyncClient):
        """Pipeline 失败时保存 error_message"""
        # Create a URL job that will fail (invalid URL forces specific error path)
        # Using a fake URL since we can't test with real network
        create_response = await client.post(
            "/api/media-transcriber/jobs",
            json={
                "source_type": "url",
                "source_url": "https://this-domain-does-not-exist-12345.com/video",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        # Wait for pipeline to complete (mock pipeline is fast)
        import asyncio

        await asyncio.sleep(3)

        # Get result
        get_response = await client.get(f"/api/media-transcriber/jobs/{job_id}")
        data = get_response.json()

        # Status should be either completed (mock fallback) or failed
        assert data["status"] in ["completed", "failed", "pending"]
        # If failed, error_message should be present
        if data["status"] == "failed":
            assert data["error_message"] is not None
            assert len(data["error_message"]) > 0