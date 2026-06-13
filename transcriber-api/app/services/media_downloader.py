"""
Media Downloader Service using yt-dlp

Downloads audio/video from publicly accessible URLs.
Never bypasses login, paywalls, DRM, or private permissions.
"""
import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from app.services.exceptions import (
    CommandNotFoundError,
    DownloadError,
    TimeoutError,
    ContentRestrictedError,
    PrivateContentError,
    AuthenticationError,
    sanitize_error_message,
)

logger = logging.getLogger(__name__)

# Default timeout for yt-dlp operations (seconds)
DEFAULT_TIMEOUT = 300


class MediaDownloader:
    """
    Media downloader using yt-dlp.

    Supports:
    - YouTube
    - Bilibili
    - Xiaoyuzhou (podcast)
    - Generic video/audio URLs

    Security principles:
    - Never bypass login, paywalls, or DRM
    - Never log or store tokens/cookies/secrets
    - Fail clearly on restricted/private content
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, output_dir: Optional[str] = None):
        self.timeout = timeout
        self.output_dir = Path(output_dir) if output_dir else Path("/tmp/media-transcriber/downloads")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_yt_dlp()

    def _check_yt_dlp(self):
        """Check if yt-dlp is installed"""
        if shutil.which("yt-dlp") is None:
            raise CommandNotFoundError("yt-dlp")

    async def download(self, url: str, format: str = "bestaudio") -> tuple[str, str]:
        """
        Download media from URL.

        Args:
            url: Publicly accessible media URL
            format: Preferred format (default: bestaudio)

        Returns:
            Tuple of (file_path, format_ext)

        Raises:
            DownloadError: If download fails
            CommandNotFoundError: If yt-dlp is not installed
            TimeoutError: If download times out
            ContentRestrictedError: If content is restricted
            PrivateContentError: If content is private
        """
        output_template = str(self.output_dir / "%(id)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "-f", format,
            "-o", output_template,
            "--no-playlist",
            "--no-warnings",
            "--newline",
            url,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                # Find downloaded file
                files = list(self.output_dir.glob("*"))
                if files:
                    # Get most recently modified file
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    return str(latest), latest.suffix.lstrip(".")

            # Parse error message (sanitized)
            error_output = sanitize_error_message(result.stderr or result.stdout)

            # Check for specific error conditions
            error_lower = error_output.lower()
            if "sign in" in error_lower or "login" in error_lower:
                raise AuthenticationError(self._get_source_type(url))
            if "age" in error_lower or "restricted" in error_lower:
                raise ContentRestrictedError("age-restricted content")
            if "private" in error_lower or "not found" in error_lower:
                raise PrivateContentError()
            if "members" in error_lower or "premium" in error_lower:
                raise ContentRestrictedError("premium content")

            raise DownloadError(f"Download failed: {error_output[:200]}")

        except subprocess.TimeoutExpired:
            raise TimeoutError("yt-dlp", self.timeout)
        except DownloadError:
            raise
        except CommandNotFoundError:
            raise
        except TimeoutError:
            raise
        except AuthenticationError:
            raise
        except ContentRestrictedError:
            raise
        except PrivateContentError:
            raise
        except Exception as e:
            raise DownloadError(f"Unexpected error: {str(e)[:100]}")

    async def get_info(self, url: str) -> dict:
        """
        Get media information without downloading.

        Args:
            url: Media URL

        Returns:
            Dict with title, duration, thumbnail info
        """
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--no-playlist",
            url,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)
                return {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "uploader": info.get("uploader", ""),
                }

            error_output = sanitize_error_message(result.stderr)
            raise DownloadError(f"Failed to get info: {error_output[:200]}")

        except subprocess.TimeoutExpired:
            raise TimeoutError("yt-dlp", 60)
        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError(f"Unexpected error: {str(e)[:100]}")

    def _get_source_type(self, url: str) -> str:
        """Infer source type from URL"""
        url_lower = url.lower()
        if "youtube" in url_lower or "youtu.be" in url_lower:
            return "YouTube"
        if "bilibili" in url_lower:
            return "Bilibili"
        if "xiaoyuzhou" in url_lower:
            return "Xiaoyuzhou"
        return "the source"

    def cleanup(self):
        """Remove downloaded files"""
        try:
            if self.output_dir.exists():
                for file in self.output_dir.glob("*"):
                    file.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup download directory: {e}")