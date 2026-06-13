"""
Job data models
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    UPLOAD = "upload"
    URL = "url"


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    DISTILLING = "distilling"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreate(BaseModel):
    """Request model for creating a transcription job"""

    source_type: SourceType = Field(..., description="Source type: 'upload' or 'url'")
    source_url: Optional[str] = Field(None, description="URL for url-type source")
    file_path: Optional[str] = Field(None, description="File path for upload-type source")
    language: str = Field(default="zh", description="Language code (default: zh)")
    output_style: str = Field(
        default="distilled_original",
        description="Output style (default: distilled_original)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_type": "url",
                    "source_url": "https://www.youtube.com/watch?v=example",
                    "language": "zh",
                },
                {
                    "source_type": "upload",
                    "file_path": "/path/to/audio.mp3",
                    "language": "zh",
                },
            ]
        }
    }


class Job(BaseModel):
    """Internal job model"""

    id: str
    source_type: SourceType
    source_url: Optional[str] = None
    file_path: Optional[str] = None
    language: str = "zh"
    output_style: str = "distilled_original"
    status: JobStatus = JobStatus.PENDING
    raw_transcript: Optional[str] = None
    cleaned_transcript: Optional[str] = None
    distilled_content: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    """Response model for job queries"""

    id: str
    source_type: SourceType
    source_url: Optional[str] = None
    file_path: Optional[str] = None
    language: str
    output_style: str
    status: JobStatus
    raw_transcript: Optional[str] = None
    cleaned_transcript: Optional[str] = None
    distilled_content: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}