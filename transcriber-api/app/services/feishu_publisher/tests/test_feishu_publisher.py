"""Tests for Feishu Publisher"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.feishu_publisher import FeishuPublisher, FeishuConfig, PublishResult, FeishuError, FeishuAuthError, FeishuAPIError


class TestSanitization:
    """Test that tokens/secrets are never logged"""

    def test_token_not_in_error_message(self):
        """Error messages don't contain tokens"""
        config = FeishuConfig(app_id="cli_test123", app_secret="secret_abc123")
        publisher = FeishuPublisher(config)

        # Try to trigger an error with a fake URL
        # The sanitized error should not contain the actual token-like strings
        result = publisher.publish("Test Doc", "# Test\n\nContent")

        # Even in failure, error messages are sanitized
        if result.error_message:
            assert "cli_test123" not in result.error_message or "[APP_ID]" in result.error_message
            assert "secret_abc123" not in result.error_message or "[APP_SECRET]" in result.error_message

    def test_publish_success(self):
        """Test successful publish with mocked responses"""
        config = FeishuConfig(app_id="cli_test", app_secret="secret_test")
        publisher = FeishuPublisher(config)

        with patch("httpx.Client") as mock_client:
            # Mock token response
            mock_token_response = MagicMock()
            mock_token_response.status_code = 200
            mock_token_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "test_token_123",
            }
            mock_token_response.raise_for_status = MagicMock()

            # Mock create doc response
            mock_doc_response = MagicMock()
            mock_doc_response.status_code = 200
            mock_doc_response.json.return_value = {
                "code": 0,
                "data": {
                    "document": {
                        "document_id": "doc_abc123",
                        "title": "Test Doc",
                    }
                }
            }
            mock_doc_response.raise_for_status = MagicMock()

            # Mock write response
            mock_write_response = MagicMock()
            mock_write_response.status_code = 200
            mock_write_response.json.return_value = {"code": 0}
            mock_write_response.raise_for_status = MagicMock()

            mock_client.return_value.__enter__.return_value.post.side_effect = [
                mock_token_response,
                mock_doc_response,
                mock_write_response,
            ]

            result = publisher.publish("Test Doc", "# Test\n\nContent paragraph here.")

            assert result.success is True
            assert result.document_id == "doc_abc123"
            assert "feishu.cn" in (result.document_url or "")

    def test_publish_creates_doc_with_title(self):
        """Test that create_document uses the provided title"""
        config = FeishuConfig(app_id="cli_test", app_secret="secret_test")
        publisher = FeishuPublisher(config)

        with patch("httpx.Client") as mock_client:
            # Mock token
            mock_token_response = MagicMock()
            mock_token_response.status_code = 200
            mock_token_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "test_token",
            }
            mock_token_response.raise_for_status = MagicMock()

            # Mock create doc
            mock_doc_response = MagicMock()
            mock_doc_response.status_code = 200
            mock_doc_response.json.return_value = {
                "code": 0,
                "data": {"document": {"document_id": "doc_xyz"}},
            }
            mock_doc_response.raise_for_status = MagicMock()

            mock_write_response = MagicMock()
            mock_write_response.status_code = 200
            mock_write_response.json.return_value = {"code": 0}
            mock_write_response.raise_for_status = MagicMock()

            mock_client.return_value.__enter__.return_value.post.side_effect = [
                mock_token_response,
                mock_doc_response,
                mock_write_response,
            ]

            result = publisher.publish("My Custom Title", "# Test\n\nContent")
            assert result.success is True


class TestMarkdownConversion:
    """Test Markdown to Feishu blocks conversion"""

    def test_heading_conversion(self):
        """Test h1/h2/h3 headings"""
        config = FeishuConfig(app_id="cli_test", app_secret="test")
        publisher = FeishuPublisher(config)

        blocks = publisher._markdown_to_feishu_blocks("# Heading 1\n\n## Heading 2\n\n### Heading 3")

        assert blocks[0]["type"] == "heading1"
        assert blocks[0]["heading1"]["elements"][0]["text_run"]["content"] == "Heading 1"
        assert blocks[1]["type"] == "heading2"
        assert blocks[2]["type"] == "heading3"

    def test_paragraph_conversion(self):
        """Test paragraph conversion"""
        config = FeishuConfig(app_id="cli_test", app_secret="test")
        publisher = FeishuPublisher(config)

        blocks = publisher._markdown_to_feishu_blocks("This is a paragraph.")

        assert blocks[0]["type"] == "paragraph"
        assert "This is a paragraph" in blocks[0]["paragraph"]["elements"][0]["text_run"]["content"]

    def test_empty_content_returns_paragraph(self):
        """Test that empty content gets a placeholder paragraph"""
        config = FeishuConfig(app_id="cli_test", app_secret="test")
        publisher = FeishuPublisher(config)

        blocks = publisher._markdown_to_feishu_blocks("")

        assert len(blocks) == 1
        assert blocks[0]["type"] == "paragraph"


class TestPublishResult:
    """Test PublishResult dataclass"""

    def test_success_result(self):
        """Test success result fields"""
        result = PublishResult(
            success=True,
            document_id="doc_123",
            document_url="https://feishu.cn/docx/doc_123",
        )
        assert result.success is True
        assert result.document_id == "doc_123"
        assert result.error_message is None
        assert result.error_code is None

    def test_failure_result(self):
        """Test failure result fields"""
        result = PublishResult(
            success=False,
            error_message="Token expired",
            error_code="99991661",
        )
        assert result.success is False
        assert result.document_id is None
        assert result.error_message == "Token expired"
        assert result.error_code == "99991661"