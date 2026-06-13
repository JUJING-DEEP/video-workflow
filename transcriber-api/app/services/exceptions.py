"""
Custom exceptions for media processing pipeline

All exceptions include clear error messages suitable for API responses.
Tokens, cookies, and secrets are NEVER included in error messages.
"""


class MediaProcessingError(Exception):
    """Base exception for media processing pipeline"""

    def __init__(self, message: str, code: str = "PROCESSING_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class DownloadError(MediaProcessingError):
    """Raised when media download fails"""

    def __init__(self, message: str, code: str = "DOWNLOAD_FAILED"):
        super().__init__(message, code)


class AudioExtractionError(MediaProcessingError):
    """Raised when audio extraction from video fails"""

    def __init__(self, message: str, code: str = "AUDIO_EXTRACTION_FAILED"):
        super().__init__(message, code)


class TranscriptionError(MediaProcessingError):
    """Raised when ASR transcription fails"""

    def __init__(self, message: str, code: str = "TRANSCRIPTION_FAILED"):
        super().__init__(message, code)


class ModelNotFoundError(TranscriptionError):
    """Raised when ASR model is not found"""

    def __init__(self, model_name: str):
        message = f"ASR model not found: {model_name}. Please download the model first."
        super().__init__(message, code="MODEL_NOT_FOUND")
        self.model_name = model_name


class CommandNotFoundError(MediaProcessingError):
    """Raised when a required command (yt-dlp, ffmpeg) is not installed"""

    def __init__(self, command: str):
        message = f"Required command not found: {command}. Please install it first."
        super().__init__(message, code="COMMAND_NOT_FOUND")
        self.command = command


class TimeoutError(MediaProcessingError):
    """Raised when a command times out"""

    def __init__(self, command: str, timeout: int):
        message = f"Command '{command}' timed out after {timeout} seconds."
        super().__init__(message, code="TIMEOUT")
        self.command = command
        self.timeout = timeout


class AuthenticationError(MediaProcessingError):
    """Raised when authentication is required but not provided"""

    def __init__(self, source_type: str):
        message = f"Content from {source_type} requires authentication. Please provide valid credentials."
        super().__init__(message, code="AUTH_REQUIRED")
        self.source_type = source_type


class ContentRestrictedError(MediaProcessingError):
    """Raised when content is age-restricted, paid, or DRM-protected"""

    def __init__(self, reason: str = "Content is restricted"):
        message = f"Content is not accessible: {reason}"
        super().__init__(message, code="CONTENT_RESTRICTED")
        self.reason = reason


class PrivateContentError(MediaProcessingError):
    """Raised when content is private"""

    def __init__(self):
        message = "Content is private or not found."
        super().__init__(message, code="PRIVATE_CONTENT")


def sanitize_error_message(message: str) -> str:
    """
    Remove any potentially sensitive information from error messages.

    This ensures tokens, cookies, and secrets are never exposed.
    """
    import re

    # Remove potential tokens (hex strings that look like API keys)
    message = re.sub(r'[a-f0-9]{32,}', '[REDACTED]', message)

    # Remove potential cookies (key=value patterns)
    message = re.sub(r'\w+=\w+;?', '', message)

    # Remove URLs with credentials
    message = re.sub(r'https?://[^@]+@', 'https://', message)

    return message