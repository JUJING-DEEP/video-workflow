"""
Real Transcription Pipeline

Uses yt-dlp for download, ffmpeg for audio extraction,
faster-whisper for transcription, and cleaning rules for text cleaning.
"""
import asyncio
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.job import JobStatus
from app.db.database import Database, JobModel
from app.services.exceptions import (
    DownloadError,
    AudioExtractionError,
    TranscriptionError,
    CommandNotFoundError,
    TimeoutError,
    AuthenticationError,
    ContentRestrictedError,
    PrivateContentError,
    MediaProcessingError,
    sanitize_error_message,
)
from app.services.distiller import distill_transcript

logger = logging.getLogger(__name__)


class TranscriptionPipeline:
    """
    Real transcription pipeline with service composition.

    State flow for URL sources:
        pending -> downloading -> transcribing -> distilling -> completed

    State flow for file sources:
        pending -> transcribing -> distilling -> completed

    State flow on failure:
        Any state -> failed (with error_message)
    """

    def __init__(self, db: Database, use_mock: bool = False):
        """
        Initialize pipeline.

        Args:
            db: Database instance
            use_mock: If True, use mock pipeline when real services unavailable
        """
        self.db = db
        self.use_mock = use_mock
        self._temp_dir = Path(tempfile.gettempdir()) / "media-transcriber"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        # Lazy-load services to avoid import errors when not installed
        self._downloader = None
        self._extractor = None
        self._transcriber = None
        self._cleaner = None

    @property
    def downloader(self):
        """Lazy-load MediaDownloader"""
        if self._downloader is None:
            from app.services.media_downloader import MediaDownloader

            try:
                self._downloader = MediaDownloader(output_dir=str(self._temp_dir / "downloads"))
            except CommandNotFoundError:
                if not self.use_mock:
                    raise
                self._downloader = None
        return self._downloader

    @property
    def extractor(self):
        """Lazy-load AudioExtractor"""
        if self._extractor is None:
            from app.services.audio_extractor import AudioExtractor

            try:
                self._extractor = AudioExtractor(output_dir=str(self._temp_dir / "audio"))
            except CommandNotFoundError:
                if not self.use_mock:
                    raise
                self._extractor = None
        return self._extractor

    @property
    def transcriber(self):
        """Lazy-load TranscriptionService"""
        if self._transcriber is None:
            from app.services.transcriber import TranscriptionService

            try:
                self._transcriber = TranscriptionService()
            except CommandNotFoundError:
                if not self.use_mock:
                    raise
                self._transcriber = None
        return self._transcriber

    @property
    def cleaner(self):
        """Lazy-load TranscriptCleaner"""
        if self._cleaner is None:
            from app.services.cleaner import TranscriptCleaner

            self._cleaner = TranscriptCleaner()
        return self._cleaner

    async def process(self, job_id: str) -> JobModel:
        """
        Process a transcription job through the pipeline.

        Args:
            job_id: Job ID to process

        Returns:
            Updated JobModel

        Raises:
            ValueError: If job not found
            DownloadError: If download fails
            AudioExtractionError: If audio extraction fails
            TranscriptionError: If transcription fails
        """
        job = await self.db.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            if job.source_type == "url":
                await self._process_url_job(job)
            else:
                await self._process_file_job(job)
        except MediaProcessingError as e:
            # Clear error message (sanitized - no tokens/secrets)
            error_msg = sanitize_error_message(str(e))
            logger.error(f"Pipeline failed for job {job_id}: {error_msg}")
            await self.db.update_job(
                job_id,
                status=JobStatus.FAILED.value,
                error_message=error_msg,
                updated_at=datetime.utcnow(),
            )
            job = await self.db.get_job(job_id)

        return job

    async def _process_url_job(self, job: JobModel) -> JobModel:
        """Process URL source: download -> extract audio -> transcribe -> clean"""
        url = job.source_url or ""

        # Step 1: Downloading
        await self.db.update_job(
            job.id,
            status=JobStatus.DOWNLOADING.value,
            updated_at=datetime.utcnow(),
        )

        try:
            if self.use_mock and self.downloader is None:
                media_path = await self._mock_download(url)
            else:
                media_path, _ = await self.downloader.download(url)
        except CommandNotFoundError:
            # Fall back to mock if yt-dlp not available
            logger.warning("yt-dlp not found, using mock download")
            media_path = await self._mock_download(url)

        # Step 2: Audio extraction
        await self.db.update_job(
            job.id,
            status=JobStatus.TRANSCRIBING.value,
            updated_at=datetime.utcnow(),
        )

        try:
            if self.use_mock and self.extractor is None:
                audio_path = await self._mock_extract_audio(media_path)
            else:
                audio_path = await self.extractor.extract(media_path)
        except CommandNotFoundError:
            logger.warning("ffmpeg not found, using mock audio extraction")
            audio_path = await self._mock_extract_audio(media_path)

        # Step 3: Transcription
        raw_transcript = await self._transcribe_audio(audio_path, job.language)

        # Step 4: Cleaning
        cleaning_result = self.cleaner.clean(raw_transcript)

        # Step 5: Distillation (mock for now - placeholder for LLM)
        distilled_content = await self._distill_text(
            cleaning_result.cleaned_text,
            job.output_style or "distilled_original",
        )

        # Mark complete
        await self.db.update_job(
            job.id,
            status=JobStatus.COMPLETED.value,
            raw_transcript=raw_transcript,
            cleaned_transcript=cleaning_result.cleaned_text,
            distilled_content=distilled_content,
            updated_at=datetime.utcnow(),
        )

        return await self.db.get_job(job.id)

    async def _process_file_job(self, job: JobModel) -> JobModel:
        """Process file source: extract audio -> transcribe -> clean"""
        file_path = job.file_path or ""

        # Step 1: Audio extraction (if it's a video file)
        await self.db.update_job(
            job.id,
            status=JobStatus.TRANSCRIBING.value,
            updated_at=datetime.utcnow(),
        )

        file_ext = Path(file_path).suffix.lower()
        is_video = file_ext in {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"}

        if is_video:
            try:
                audio_path = await self.extractor.extract(file_path)
            except CommandNotFoundError:
                audio_path = await self._mock_extract_audio(file_path)
        else:
            # Already an audio file
            audio_path = file_path

        # Step 2: Transcription
        raw_transcript = await self._transcribe_audio(audio_path, job.language)

        # Step 3: Cleaning
        cleaning_result = self.cleaner.clean(raw_transcript)

        # Step 4: Distillation
        distilled_content = await self._distill_text(
            cleaning_result.cleaned_text,
            job.output_style or "distilled_original",
        )

        # Mark complete
        await self.db.update_job(
            job.id,
            status=JobStatus.COMPLETED.value,
            raw_transcript=raw_transcript,
            cleaned_transcript=cleaning_result.cleaned_text,
            distilled_content=distilled_content,
            updated_at=datetime.utcnow(),
        )

        return await self.db.get_job(job.id)

    async def _transcribe_audio(self, audio_path: str, language: str) -> str:
        """
        Transcribe audio file.

        Uses faster-whisper if available, otherwise returns mock transcript.
        """
        try:
            if self.use_mock and self.transcriber is None:
                return await self._mock_transcribe(audio_path, language)
            else:
                result = await self.transcriber.transcribe(audio_path, language)
                return result.text
        except CommandNotFoundError:
            logger.warning("faster-whisper not found, using mock transcription")
            return await self._mock_transcribe(audio_path, language)

    async def _distill_text(self, cleaned_text: str, output_style: str) -> str:
        """
        Distill cleaned text into shareable format using distiller.

        Args:
            cleaned_text: Cleaned transcript text
            output_style: Output style (default: distilled_original)

        Returns:
            Distilled text content

        Raises:
            Exception: If distillation fails, propagates error with clear message
        """
        if not cleaned_text:
            return ""

        try:
            result = distill_transcript(cleaned_text, output_style)

            # Log warnings but don't fail on quality issues
            for warning in result.warnings:
                logger.warning(f"Distillation warning for job: {warning}")

            # Log quality issues but don't fail - distiller still produces output
            if result.issues:
                issue_msgs = [f"{i.category}: {i.description}" for i in result.issues]
                logger.warning(f"Distillation quality issues: {issue_msgs}")

            return result.distilled_text

        except Exception as e:
            error_msg = f"Distillation failed: {str(e)}"
            logger.error(error_msg)
            raise MediaProcessingError(error_msg, code="DISTILLATION_FAILED")

    # ============================================================
    # Mock fallbacks (when real services unavailable)
    # ============================================================

    async def _mock_download(self, url: str) -> str:
        """Mock download when yt-dlp unavailable"""
        await asyncio.sleep(0.5)
        # Create a placeholder file
        mock_file = self._temp_dir / "downloads" / f"mock_{hash(url)}.txt"
        mock_file.parent.mkdir(parents=True, exist_ok=True)
        mock_file.write_text(f"[MOCK] Downloaded content from {url}")
        return str(mock_file)

    async def _mock_extract_audio(self, input_path: str) -> str:
        """Mock audio extraction when ffmpeg unavailable"""
        await asyncio.sleep(0.3)
        # Return the input path as-is for mock
        return input_path

    async def _mock_transcribe(self, audio_path: str, language: str) -> str:
        """Mock transcription when faster-whisper unavailable"""
        await asyncio.sleep(0.5)

        # Try to read the file as text (for testing with text files)
        try:
            path = Path(audio_path)
            if path.exists() and path.suffix == ".txt":
                return path.read_text()
        except Exception:
            pass

        return f"[MOCK] Transcript from {audio_path} (language: {language})"

    def cleanup(self):
        """Clean up temporary files"""
        try:
            import shutil

            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")