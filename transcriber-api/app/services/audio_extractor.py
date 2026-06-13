"""
Audio Extractor Service using ffmpeg

Extracts audio from video files, converts to standardized format.
"""
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from app.services.exceptions import (
    CommandNotFoundError,
    AudioExtractionError,
    TimeoutError,
)

logger = logging.getLogger(__name__)

# Default timeout for ffmpeg operations (seconds)
DEFAULT_TIMEOUT = 300


class AudioExtractor:
    """
    Audio extraction and conversion using ffmpeg.

    Standard output format:
    - Codec: PCM S16LE (pcm_s16le)
    - Sample rate: 16000 Hz
    - Channels: 1 (mono)
    - Format: WAV

    Supported input formats:
    - MP4, MKV, AVI, MOV (video)
    - MP3, M4A, AAC, OGG (audio)
    - Any format supported by ffmpeg
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, output_dir: Optional[str] = None):
        self.timeout = timeout
        self.output_dir = Path(output_dir) if output_dir else Path("/tmp/media-transcriber/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if ffmpeg is installed"""
        if shutil.which("ffmpeg") is None:
            raise CommandNotFoundError("ffmpeg")

    async def extract(
        self,
        input_path: str,
        output_format: str = "wav",
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> str:
        """
        Extract audio from video file and convert to specified format.

        Args:
            input_path: Path to input media file
            output_format: Output format (wav, mp3, m4a)
            sample_rate: Sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)

        Returns:
            Path to output audio file

        Raises:
            AudioExtractionError: If extraction fails
            CommandNotFoundError: If ffmpeg is not installed
            TimeoutError: If process times out
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise AudioExtractionError(f"Input file not found: {input_path}")

        # Generate output filename
        output_name = f"{input_path.stem}_audio.{output_format}"
        output_path = self.output_dir / output_name

        # Build ffmpeg command (list args, no shell=True)
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-vn",  # No video
            "-acodec", "pcm_s16le" if output_format == "wav" else "copy",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-y",  # Overwrite output
            str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0 and output_path.exists():
                return str(output_path)

            # Parse ffmpeg error
            error_msg = result.stderr or "Unknown ffmpeg error"
            if "Invalid data" in error_msg:
                raise AudioExtractionError("Input file is corrupted or unsupported format")
            if "Output file" in error_msg and "already exists" in error_msg:
                raise AudioExtractionError("Output file already exists (should not happen)")

            raise AudioExtractionError(f"ffmpeg failed: {error_msg[:200]}")

        except subprocess.TimeoutExpired:
            raise TimeoutError("ffmpeg", self.timeout)
        except AudioExtractionError:
            raise
        except CommandNotFoundError:
            raise
        except Exception as e:
            raise AudioExtractionError(f"Unexpected error: {str(e)[:100]}")

    async def get_duration(self, file_path: str) -> float:
        """
        Get duration of audio/video file in seconds.

        Args:
            file_path: Path to media file

        Returns:
            Duration in seconds
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return float(result.stdout.strip())

            return 0.0

        except Exception:
            return 0.0

    def cleanup(self):
        """Remove extracted audio files"""
        try:
            if self.output_dir.exists():
                for file in self.output_dir.glob("*"):
                    file.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup audio directory: {e}")