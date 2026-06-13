"""
Mock Transcription Pipeline

This module provides the mock implementation for the transcription pipeline.
Real implementations using yt-dlp, ffmpeg, and whisper will be added later.
"""
import asyncio
import logging
import random
import uuid
from datetime import datetime
from typing import Optional

from app.models.job import JobStatus
from app.db.database import Database, JobModel

logger = logging.getLogger(__name__)


class TranscriptionPipeline:
    """
    Mock transcription pipeline.

    For URL sources: simulates state transitions without real download.
    For file sources: reads local text file as mock transcript.
    """

    def __init__(self, db: Database):
        self.db = db

    async def process(self, job_id: str) -> JobModel:
        """
        Process a transcription job through the mock pipeline.

        State flow for URL sources:
            pending -> downloading -> transcribing -> distilling -> completed

        State flow for file sources:
            pending -> transcribing -> distilling -> completed

        State flow on failure:
            Any state -> failed (with error_message)
        """
        job = await self.db.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            if job.source_type == "url":
                await self._process_url_job(job)
            else:
                await self._process_file_job(job)
        except Exception as e:
            logger.error(f"Pipeline failed for job {job_id}: {e}")
            await self.db.update_job(
                job_id,
                status="failed",
                error_message=str(e),
                updated_at=datetime.utcnow(),
            )
            job = await self.db.get_job(job_id)

        return job

    async def _process_url_job(self, job: JobModel) -> JobModel:
        """Process URL source: simulate download, transcribe, distill"""
        # Step 1: Downloading
        await self.db.update_job(
            job.id, status=JobStatus.DOWNLOADING, updated_at=datetime.utcnow()
        )
        await asyncio.sleep(0.5)  # Simulate download time

        # Step 2: Transcribing (mock - no real ASR)
        await self.db.update_job(
            job.id, status=JobStatus.TRANSCRIBING, updated_at=datetime.utcnow()
        )
        await asyncio.sleep(0.5)  # Simulate ASR time

        # Mock raw transcript
        mock_raw_transcript = f"[MOCK] Raw transcript for {job.source_url or 'unknown URL'}..."
        await self.db.update_job(
            job.id,
            status=JobStatus.DISTILLING,
            raw_transcript=mock_raw_transcript,
            updated_at=datetime.utcnow(),
        )
        await asyncio.sleep(0.5)  # Simulate distillation time

        # Step 3: Distilling (mock)
        mock_distilled = f"# 主题\n\n这是来自 {job.source_url or 'URL'} 的提纯稿。\n\n## 内容段落\n\n原始内容已清洗整理，保留了关键信息。"
        await self.db.update_job(
            job.id,
            status=JobStatus.COMPLETED,
            cleaned_transcript=f"[CLEANED] {mock_raw_transcript}",
            distilled_content=mock_distilled,
            updated_at=datetime.utcnow(),
        )

        return await self.db.get_job(job.id)

    async def _process_file_job(self, job: JobModel) -> JobModel:
        """Process file source: read local text file as mock transcript"""
        # Step 1: Transcribing (read local file as mock)
        await self.db.update_job(
            job.id, status=JobStatus.TRANSCRIBING, updated_at=datetime.utcnow()
        )
        await asyncio.sleep(0.3)

        # Read local text file as mock transcript
        file_path = job.file_path or ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except (FileNotFoundError, PermissionError):
            file_content = f"[MOCK] File content from {file_path}"

        raw_transcript = file_content if file_content.strip() else f"[MOCK] Transcript from {file_path}"

        await self.db.update_job(
            job.id,
            status=JobStatus.DISTILLING,
            raw_transcript=raw_transcript,
            updated_at=datetime.utcnow(),
        )
        await asyncio.sleep(0.3)

        # Step 2: Distilling
        mock_distilled = f"# 主题\n\n{raw_transcript}\n\n## 内容整理\n\n内容已整理为提纯稿格式。"
        await self.db.update_job(
            job.id,
            status=JobStatus.COMPLETED,
            cleaned_transcript=f"[CLEANED] {raw_transcript[:100]}...",
            distilled_content=mock_distilled,
            updated_at=datetime.utcnow(),
        )

        return await self.db.get_job(job.id)


# ============================================================
# Real service interfaces (to be implemented)
# ============================================================


async def download_media(url: str, output_dir: str) -> str:
    """
    Download media from URL using yt-dlp.

    Args:
        url: Media URL (YouTube, B站, etc.)
        output_dir: Directory to save downloaded file

    Returns:
        Path to downloaded file

    Raises:
        DownloadError: If download fails
    """
    # TODO: Implement with yt-dlp
    # Example:
    # import yt_dlp
    # ydl_opts = {'format': 'bestaudio/best', 'outtmpl': f'{output_dir}/%(id)s.%(ext)s'}
    # with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    #     info = ydl.extract_info(url, download=True)
    #     return ydl.prepare_filename(info)
    raise NotImplementedError("Real yt-dlp download not yet implemented")


async def extract_audio(video_path: str, output_path: str) -> str:
    """
    Extract audio from video file using ffmpeg.

    Args:
        video_path: Path to video file
        output_path: Path to output audio file

    Returns:
        Path to extracted audio file

    Raises:
        ConversionError: If conversion fails
    """
    # TODO: Implement with ffmpeg
    # Example:
    # import subprocess
    # result = subprocess.run([
    #     'ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le',
    #     '-ar', '16000', '-ac', '1', output_path
    # ], capture_output=True)
    # if result.returncode != 0:
    #     raise ConversionError(result.stderr.decode())
    # return output_path
    raise NotImplementedError("Real ffmpeg audio extraction not yet implemented")


async def transcribe_audio(audio_path: str, language: str = "zh") -> dict:
    """
    Transcribe audio using faster-whisper.

    Args:
        audio_path: Path to audio file
        language: Language code (default: zh)

    Returns:
        Dict with raw_transcript, language, duration, confidence

    Raises:
        TranscriptionError: If transcription fails
    """
    # TODO: Implement with faster-whisper
    # Example:
    # from faster_whisper import WhisperModel
    # model = WhisperModel("medium", device="cuda" if torch.cuda.is_available() else "cpu")
    # segments, info = model.transcribe(audio_path, language=language if language != "zh" else "zh")
    # text = " ".join([seg.text for seg in segments])
    # return {
    #     "raw_transcript": text,
    #     "language": info.language,
    #     "duration": info.duration,
    #     "confidence": info.segments[0].no_speech_prob if info.segments else 0.0
    # }
    raise NotImplementedError("Real Whisper transcription not yet implemented")


async def clean_transcript(raw_text: str) -> str:
    """
    Clean transcript by removing timestamps, speaker labels, etc.

    Args:
        raw_text: Raw transcript text

    Returns:
        Cleaned transcript text
    """
    # TODO: Implement with cleaning rules
    raise NotImplementedError("Real transcript cleaning not yet implemented")


async def distill_transcript(cleaned_text: str, output_style: str = "distilled_original") -> str:
    """
    Distill transcript into shareable formatted text.

    Args:
        cleaned_text: Cleaned transcript text
        output_style: Output style (default: distilled_original)

    Returns:
        Distilled content in structured format
    """
    # TODO: Implement with LLM distillation
    raise NotImplementedError("Real LLM distillation not yet implemented")