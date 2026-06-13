"""
Jobs API routes
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.db.database import Database, get_db
from app.models.job import JobCreate, JobResponse, JobStatus, SourceType
from app.services.pipeline import TranscriptionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media-transcriber", tags=["jobs"])


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
        created_at=job.created_at,
        updated_at=job.updated_at,
    )