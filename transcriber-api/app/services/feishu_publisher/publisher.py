"""
Feishu Publisher Service

Creates Feishu documents and writes Markdown content.
Never logs tokens, secrets, or access tokens.
"""
import logging
import time
from typing import Optional

import httpx

from app.services.feishu_publisher.types import FeishuConfig, FeishuDocument, PublishResult

logger = logging.getLogger(__name__)

# Feishu API endpoints
LARK_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
LARK_CREATE_DOC_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
LARK_BLOCKS_URL_TEMPLATE = "https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks"


class FeishuPublisher:
    """
    Publishes content to Feishu documents.

    Security principles:
    - Never log tokens or secrets
    - Error messages are sanitized
    """

    def __init__(self, config: FeishuConfig):
        self.config = config
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    def _sanitize_error(self, message: str) -> str:
        """Remove potentially sensitive data from error messages"""
        import re
        # Remove hex tokens >= 16 chars
        sanitized = re.sub(r'[a-f0-9]{16,}', '[REDACTED]', message)
        # Remove tokens, secrets, app_id near keywords
        patterns = [
            r'(app_secret\s*[=:]\s*)[^\s,}]+',
            r'(tenant_access_token\s*[=:]\s*)[^\s,}]+',
            r'(folder_token\s*[=:]\s*)[^\s,}]+',
            r'(bearer\s+)[^\s,}]+',
            r'(token\s+)[^\s,}]+',
            r'(password\s*[=:]\s*)[^\s,}]+',
        ]
        for p in patterns:
            sanitized = re.sub(p, r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
        return sanitized

    def _get_token(self) -> str:
        """
        Get tenant access token.
        Caches token until expiry.
        """
        # Check if cached token is still valid (tokens last 2 hours)
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        url = LARK_TOKEN_URL
        payload = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 0:
                    error_msg = self._sanitize_error(data.get("msg", "Token request failed"))
                    raise FeishuAuthError(error_msg, data.get("code"))

                self._token = data["tenant_access_token"]
                # Token typically valid for 2 hours
                self._token_expiry = time.time() + 7200
                return self._token

        except httpx.HTTPError as e:
            error = self._sanitize_error(str(e))
            raise FeishuAuthError(f"Token request failed: {error}")

    def create_document(self, title: str) -> FeishuDocument:
        """
        Create a new Feishu document.

        Args:
            title: Document title

        Returns:
            FeishuDocument with id and url

        Raises:
            FeishuAuthError: If authentication fails
            FeishuAPIError: If document creation fails
        """
        token = self._get_token()
        url = LARK_CREATE_DOC_URL
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"title": title}
        if self.config.folder_token:
            payload["folder_token"] = self.config.folder_token

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 0:
                    error_msg = self._sanitize_error(data.get("msg", "Create document failed"))
                    raise FeishuAPIError(error_msg, data.get("code"))

                doc_data = data["data"]["document"]
                doc_id = doc_data["document_id"]
                # Feishu doc URL format
                doc_url = f"https://feishu.cn/docx/{doc_id}"

                return FeishuDocument(
                    document_id=doc_id,
                    document_url=doc_url,
                    title=title,
                )

        except httpx.HTTPError as e:
            error = self._sanitize_error(str(e))
            raise FeishuAPIError(f"Create document failed: {error}")

    def write_content(self, document_id: str, markdown_content: str) -> bool:
        """
        Write Markdown content to a Feishu document.

        Args:
            document_id: Feishu document ID
            markdown_content: Content to write

        Returns:
            True if successful

        Raises:
            FeishuAPIError: If write fails
        """
        token = self._get_token()
        url = LARK_BLOCKS_URL_TEMPLATE.format(document_id=document_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Convert markdown to Feishu blocks
        blocks = self._markdown_to_feishu_blocks(markdown_content)
        payload = {"children": blocks, "index": -1}

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 0:
                    error_msg = self._sanitize_error(data.get("msg", "Write content failed"))
                    raise FeishuAPIError(error_msg, data.get("code"))

                return True

        except httpx.HTTPError as e:
            error = self._sanitize_error(str(e))
            raise FeishuAPIError(f"Write content failed: {error}")

    def _markdown_to_feishu_blocks(self, markdown: str) -> list:
        """
        Convert Markdown to Feishu block format.

        Simplified conversion - handles headings and paragraphs.
        """
        blocks = []
        lines = markdown.split("\n")
        in_code_block = False

        for line in lines:
            line = line.rstrip()

            if line.startswith("```"):
                in_code_block = not in_code_block
                continue

            if in_code_block:
                blocks.append({"type": "code", "code": {"content": line}})
                continue

            if line.startswith("# "):
                blocks.append({
                    "type": "heading1",
                    "heading1": {"elements": [{"type": "text_run", "text_run": {"content": line[2:]}}]},
                })
            elif line.startswith("## "):
                blocks.append({
                    "type": "heading2",
                    "heading2": {"elements": [{"type": "text_run", "text_run": {"content": line[3:]}}]},
                })
            elif line.startswith("### "):
                blocks.append({
                    "type": "heading3",
                    "heading3": {"elements": [{"type": "text_run", "text_run": {"content": line[4:]}}]},
                })
            elif line.startswith("-"):
                blocks.append({
                    "type": "bullet",
                    "bullet": {"elements": [{"type": "text_run", "text_run": {"content": line[1:].strip()}}]},
                })
            elif line.strip():
                blocks.append({
                    "type": "paragraph",
                    "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": line}}]},
                })

        # Always end with a paragraph to ensure document isn't empty
        if not blocks:
            blocks.append({
                "type": "paragraph",
                "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": ""}}]},
            })

        return blocks

    def health_check(self) -> dict:
        """
        Verify Feishu credentials and connectivity.

        Returns:
            {"status": "healthy"} or {"status": "unhealthy", "reason": "..."}
        """
        if not self.config.app_id:
            return {"status": "unhealthy", "reason": "app_id not configured"}

        if not self.config.app_secret:
            return {"status": "unhealthy", "reason": "app_secret not configured"}

        try:
            self._get_token()
            return {"status": "healthy"}
        except FeishuError as e:
            return {"status": "unhealthy", "reason": e.message}
        except Exception as e:
            return {"status": "unhealthy", "reason": self._sanitize_error(str(e))}

    def publish(self, title: str, content: str) -> PublishResult:
        """
        Create a Feishu document and write content.

        Args:
            title: Document title
            content: Markdown content

        Returns:
            PublishResult with document_id/url or error
        """
        try:
            doc = self.create_document(title)
            self.write_content(doc.document_id, content)
            return PublishResult(
                success=True,
                document_id=doc.document_id,
                document_url=doc.document_url,
            )
        except FeishuError as e:
            return PublishResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )
        except Exception as e:
            return PublishResult(
                success=False,
                error_message=self._sanitize_error(str(e)),
            )


class FeishuError(Exception):
    """Base Feishu error"""
    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(message)


class FeishuAuthError(FeishuError):
    """Authentication error"""
    pass


class FeishuAPIError(FeishuError):
    """API error"""
    pass
