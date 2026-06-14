"""
Jobs API routes
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.db.database import Database, get_db
from app.models.job import JobCreate, JobResponse, JobStatus, SourceType
from app.services.pipeline import TranscriptionPipeline

import os

from app.services.feishu_publisher import FeishuPublisher, FeishuConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media-transcriber", tags=["jobs"])


class FeishuHealthResult(BaseModel):
    """Response model for Feishu health check"""

    status: str
    reason: Optional[str] = None


@router.get("/health/feishu", response_model=FeishuHealthResult)
async def get_feishu_health() -> FeishuHealthResult:
    """
    Check Feishu API connectivity and credentials.

    Returns healthy status if app_id/app_secret are configured
    and a valid tenant_access_token can be obtained.
    """
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")

    if not app_id or not app_secret:
        return FeishuHealthResult(
            status="unhealthy",
            reason="FEISHU_APP_ID and FEISHU_APP_SECRET must be configured",
        )

    folder_token = os.environ.get("FEISHU_FOLDER_TOKEN")
    config = FeishuConfig(app_id=app_id, app_secret=app_secret, folder_token=folder_token)
    publisher = FeishuPublisher(config)
    result = publisher.health_check()
    return FeishuHealthResult(status=result["status"], reason=result.get("reason"))


class FeishuPublishResult(BaseModel):
    """Response model for Feishu publish operation"""

    job_id: str
    status: str
    document_id: Optional[str] = None
    document_url: Optional[str] = None
    error_message: Optional[str] = None


def generate_job_id() -> str:
    """Generate a unique job ID"""
    return f"job_{uuid.uuid4().hex[:12]}"


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job_create: JobCreate) -> JobResponse:
    """
    Create a new transcription job.

    - **source_type**: 'upload' or 'url'
    - **source_url**: URL for url-type source
    - **file_path**: File path for upload-type source
    - **language**: Language code (default: zh)
    - **output_style**: Output style (default: distilled_original)
    """
    db = get_db()

    # Validate: url type requires source_url
    if job_create.source_type == SourceType.URL:
        if not job_create.source_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_url is required for url-type source",
            )
    # Validate: upload type requires file_path
    elif job_create.source_type == SourceType.UPLOAD:
        if not job_create.file_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_path is required for upload-type source",
            )

    # Create job
    job_id = generate_job_id()
    job_data = {
        "id": job_id,
        "source_type": job_create.source_type.value,
        "source_url": job_create.source_url,
        "file_path": job_create.file_path,
        "language": job_create.language,
        "output_style": job_create.output_style,
        "status": JobStatus.PENDING.value,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    try:
        job = await db.create_job(job_data)
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job",
        )

    # Run mock pipeline in background (async simulation)
    asyncio.create_task(_run_pipeline(job_id))

    return _to_response(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Get transcription job by ID"""
    db = get_db()
    job = await db.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return _to_response(job)


@router.post("/jobs/{job_id}/publish/feishu", response_model=FeishuPublishResult)
async def publish_job_to_feishu(job_id: str) -> FeishuPublishResult:
    """
    Publish job content to Feishu document.

    Requires the job to have distilled_content.
    """
    db = get_db()
    job = await db.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Check for distilled content
    if not job.distilled_content:
        return FeishuPublishResult(
            job_id=job_id,
            status="error",
            error_message="Job has no distilled content",
        )

    # Get Feishu config from environment
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")

    if not app_id or not app_secret:
        return FeishuPublishResult(
            job_id=job_id,
            status="error",
            error_message="FEISHU_APP_ID and FEISHU_APP_SECRET must be configured",
        )

    try:
        config = FeishuConfig(app_id=app_id, app_secret=app_secret)
        publisher = FeishuPublisher(config)

        # Build title from job metadata
        title = f"转录任务 {job_id}"

        # Publish (create document + write content)
        result = publisher.publish(title, job.distilled_content)

        if result.success:
            # Update job with Feishu document info
            now = datetime.utcnow()
            await db.update_job(
                job_id,
                feishu_document_id=result.document_id,
                feishu_document_url=result.document_url,
                published_at=now,
            )
            return FeishuPublishResult(
                job_id=job_id,
                status="success",
                document_id=result.document_id,
                document_url=result.document_url,
            )
        else:
            from app.services.exceptions import sanitize_error_message
            return FeishuPublishResult(
                job_id=job_id,
                status="error",
                error_message=sanitize_error_message(result.error_message or "Unknown error"),
            )

    except Exception as e:
        # Sanitize any exception before returning
        from app.services.exceptions import sanitize_error_message
        safe_msg = sanitize_error_message(str(e))
        return FeishuPublishResult(
            job_id=job_id,
            status="error",
            error_message=f"Feishu publish failed: {safe_msg}",
        )


async def _run_pipeline(job_id: str):
    """Run the transcription pipeline (with mock fallback)"""
    db = get_db()
    pipeline = TranscriptionPipeline(db, use_mock=True)
    try:
        await pipeline.process(job_id)
    except Exception as e:
        from app.services.exceptions import sanitize_error_message

        error_msg = sanitize_error_message(str(e))
        logger.error(f"Pipeline error for job {job_id}: {error_msg}")
        await db.update_job(
            job_id,
            status="failed",
            error_message=error_msg,
            updated_at=datetime.utcnow(),
        )


def _to_response(job) -> JobResponse:
    """Convert JobModel to JobResponse"""
    return JobResponse(
        id=job.id,
        source_type=SourceType(job.source_type),
        source_url=job.source_url,
        file_path=job.file_path,
        language=job.language,
        output_style=job.output_style,
        status=JobStatus(job.status),
        raw_transcript=job.raw_transcript,
        cleaned_transcript=job.cleaned_transcript,
        distilled_content=job.distilled_content,
        error_message=job.error_message,
        feishu_document_id=job.feishu_document_id,
        feishu_document_url=job.feishu_document_url,
        published_at=job.published_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )