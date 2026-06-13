"""
Transcription Service using faster-whisper

Abstract interface with concrete faster-whisper implementation.
"""
import logging
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.services.exceptions import (
    CommandNotFoundError,
    TranscriptionError,
    ModelNotFoundError,
    TimeoutError,
)

logger = logging.getLogger(__name__)

# Default timeout for transcription (seconds)
DEFAULT_TIMEOUT = 600


@dataclass
class TranscriptionResult:
    """Result from transcription"""

    text: str
    language: str
    duration: float
    confidence: float


class Transcriber(ABC):
    """Abstract transcriber interface"""

    @abstractmethod
    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> TranscriptionResult:
        """Transcribe audio file"""
        raise NotImplementedError


class FasterWhisperTranscriber(Transcriber):
    """
    Transcription using faster-whisper.

    Supports model sizes: tiny, base, small, medium, large-v1, large-v2
    """

    def __init__(
        self,
        model_name: str = "medium",
        model_dir: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize faster-whisper transcriber.

        Args:
            model_name: Model size (default: medium)
            model_dir: Directory to cache models
            timeout: Timeout for transcription in seconds
        """
        self.model_name = model_name
        self.model_dir = model_dir or str(tempfile.gettempdir())
        self.timeout = timeout
        self._check_modelhub()

    def _check_modelhub(self):
        """Check if faster-whisper CLI is available"""
        if shutil.which("faster-whisper") is None:
            # Check if we can use python -m faster_whisper
            try:
                result = subprocess.run(
                    ["python", "-c", "from faster_whisper import WhisperModel"],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    raise CommandNotFoundError("faster-whisper")
            except Exception:
                raise CommandNotFoundError("faster-whisper")

    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> TranscriptionResult:
        """
        Transcribe audio using faster-whisper.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'zh', 'en') or None for auto-detection

        Returns:
            TranscriptionResult with text, language, duration, confidence

        Raises:
            TranscriptionError: If transcription fails
            ModelNotFoundError: If model is not found
            TimeoutError: If transcription times out
        """
        # Build transcription command using Python inline script
        # This avoids shell=True and provides structured output
        language_arg = repr(language) if language else "None"

        code = f"""
import sys
from faster_whisper import WhisperModel

try:
    model = WhisperModel(
        "{self.model_name}",
        device="cpu",
        compute_type="int8",
        download_root="{self.model_dir}"
    )

    segments, info = model.transcribe(
        "{audio_path}",
        language={language_arg} if {language_arg} else None,
        temperature=0.0,
    )

    full_text = []
    for segment in segments:
        full_text.append(segment.text)

    print("TEXT:" + "".join(full_text))
    print("LANG:" + str(info.language))
    print("DURATION:" + str(info.duration))
    print("CONFIDENCE:" + str(info.language_probability))
    sys.exit(0)
except FileNotFoundError as e:
    if "not found" in str(e).lower() or "download" in str(e).lower():
        print("MODEL_NOT_FOUND:" + str(e), file=sys.stderr)
        sys.exit(1)
    raise
except Exception as e:
    print("ERROR:" + str(e), file=sys.stderr)
    sys.exit(1)
"""

        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return self._parse_output(result.stdout)

            # Check for model not found
            if "MODEL_NOT_FOUND" in result.stderr or result.returncode == 1:
                raise ModelNotFoundError(self.model_name)

            # Parse error
            error_lines = [line for line in result.stderr.split("\n") if line.startswith("ERROR:")]
            error_msg = error_lines[0] if error_lines else result.stderr[:200]
            raise TranscriptionError(error_msg)

        except subprocess.TimeoutExpired:
            raise TimeoutError("faster-whisper", self.timeout)
        except TranscriptionError:
            raise
        except ModelNotFoundError:
            raise
        except CommandNotFoundError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Unexpected error: {str(e)[:100]}")

    def _parse_output(self, output: str) -> TranscriptionResult:
        """Parse faster-whisper output"""
        text = ""
        lang = "zh"
        duration = 0.0
        confidence = 0.9

        for line in output.split("\n"):
            if line.startswith("TEXT:"):
                text = line[5:]
            elif line.startswith("LANG:"):
                lang = line[5:]
            elif line.startswith("DURATION:"):
                try:
                    duration = float(line[9:])
                except ValueError:
                    pass
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line[11:])
                except ValueError:
                    pass

        return TranscriptionResult(
            text=text,
            language=lang,
            duration=duration,
            confidence=confidence,
        )


class TranscriptionService:
    """
    Transcription service with engine selection.

    Currently uses faster-whisper only.
    """

    def __init__(self, model_name: str = "medium", model_dir: Optional[str] = None):
        self.engine = FasterWhisperTranscriber(model_name=model_name, model_dir=model_dir)

    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> TranscriptionResult:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Language code or None for auto-detection

        Returns:
            TranscriptionResult
        """
        return await self.engine.transcribe(audio_path, language)