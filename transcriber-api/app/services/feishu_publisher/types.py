"""
Feishu Publisher types
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FeishuConfig:
    """Feishu app configuration"""
    app_id: str
    app_secret: str
    folder_token: Optional[str] = None


@dataclass
class FeishuDocument:
    """Created Feishu document"""
    document_id: str
    document_url: str
    title: str


@dataclass
class PublishResult:
    """Result of publishing to Feishu"""
    success: bool
    document_id: Optional[str] = None
    document_url: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
