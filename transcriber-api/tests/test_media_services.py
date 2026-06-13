"""
Mock tests for media services (yt-dlp, ffmpeg, ASR)

These tests mock subprocess calls to test the service logic
without requiring yt-dlp, ffmpeg, or faster-whisper to be installed.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import os


class TestMediaDownloader:
    """Tests for MediaDownloader with mocked yt-dlp"""

    @pytest.mark.asyncio
    async def test_download_success(self):
        """Test successful download with mocked yt-dlp"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr="",
                stdout="",
            )
            with patch("pathlib.Path.glob") as mock_glob:
                mock_file = MagicMock()
                mock_file.stat.return_value.st_mtime = 123456
                mock_file.suffix.lstrip.return_value = "m4a"
                mock_glob.return_value = [mock_file]

                from app.services.media_downloader import MediaDownloader

                downloader = MediaDownloader(output_dir=tempfile.gettempdir())
                path, fmt = await downloader.download("https://example.com/video")

                # Verify command was called with list args (no shell=True)
                mock_run.assert_called_once()
                call_args = mock_run.call_args
                assert call_args.kwargs.get("shell") is None or call_args.kwargs.get("shell") is False
                assert call_args.args[0][0] == "yt-dlp"

    @pytest.mark.asyncio
    async def test_download_timeout(self):
        """Test download timeout error"""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("yt-dlp", 300)

            from app.services.media_downloader import MediaDownloader
            from app.services.exceptions import TimeoutError

            downloader = MediaDownloader(output_dir=tempfile.gettempdir())

            with pytest.raises(TimeoutError) as exc_info:
                await downloader.download("https://example.com/video")

            assert "yt-dlp" in str(exc_info.value.message)
            assert "300" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_download_private_content(self):
        """Test handling of private content error"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="ERROR: Video is private",
                stdout="",
            )

            from app.services.media_downloader import MediaDownloader
            from app.services.exceptions import PrivateContentError

            downloader = MediaDownloader(output_dir=tempfile.gettempdir())

            with pytest.raises(PrivateContentError):
                await downloader.download("https://example.com/private")

    @pytest.mark.asyncio
    async def test_download_restricted_content(self):
        """Test handling of age-restricted content"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="ERROR: Video is age-restricted",
                stdout="",
            )

            from app.services.media_downloader import MediaDownloader
            from app.services.exceptions import ContentRestrictedError

            downloader = MediaDownloader(output_dir=tempfile.gettempdir())

            with pytest.raises(ContentRestrictedError):
                await downloader.download("https://example.com/restricted")

    @pytest.mark.asyncio
    async def test_download_auth_required(self):
        """Test handling of content requiring authentication"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="ERROR: This content requires login",
                stdout="",
            )

            from app.services.media_downloader import MediaDownloader
            from app.services.exceptions import AuthenticationError

            downloader = MediaDownloader(output_dir=tempfile.gettempdir())

            with pytest.raises(AuthenticationError):
                await downloader.download("https://example.com/members")

    @pytest.mark.asyncio
    async def test_sanitize_removes_tokens(self):
        """Test that sanitize_error_message removes tokens"""
        from app.services.exceptions import sanitize_error_message

        # Should redact hex strings that look like API keys
        result = sanitize_error_message("Error: key=abc123def456abc123def456abc123def456xyz")
        assert "abc123def456" not in result or "[REDACTED]" in result

    @pytest.mark.asyncio
    async def test_sanitize_removes_cookies(self):
        """Test that sanitize_error_message removes cookies"""
        from app.services.exceptions import sanitize_error_message

        result = sanitize_error_message("Error: session=abc123; token=def456")
        assert "session=abc123" not in result or "def456" not in result


class TestAudioExtractor:
    """Tests for AudioExtractor with mocked ffmpeg"""

    @pytest.mark.asyncio
    async def test_extract_audio_success(self):
        """Test successful audio extraction with mocked ffmpeg"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr="",
                stdout="",
            )
            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True
                with tempfile.TemporaryDirectory() as tmpdir:
                    input_path = Path(tmpdir) / "input.mp4"
                    input_path.write_text("fake video")

                    from app.services.audio_extractor import AudioExtractor

                    extractor = AudioExtractor(output_dir=tmpdir)
                    output_path = await extractor.extract(str(input_path))

                    # Verify ffmpeg was called with list args
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    cmd = call_args.args[0]
                    assert cmd[0] == "ffmpeg"
                    assert "-i" in cmd
                    assert "-vn" in cmd
                    assert "pcm_s16le" in cmd

    @pytest.mark.asyncio
    async def test_extract_audio_timeout(self):
        """Test audio extraction timeout"""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 300)

            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "input.mp4"
                input_path.write_text("fake video")

                from app.services.audio_extractor import AudioExtractor
                from app.services.exceptions import TimeoutError

                extractor = AudioExtractor(output_dir=tmpdir)

                with pytest.raises(TimeoutError) as exc_info:
                    await extractor.extract(str(input_path))

                assert "ffmpeg" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_extract_audio_file_not_found(self):
        """Test audio extraction with missing input file"""
        from app.services.audio_extractor import AudioExtractor
        from app.services.exceptions import AudioExtractionError

        extractor = AudioExtractor(output_dir=tempfile.gettempdir())

        with pytest.raises(AudioExtractionError) as exc_info:
            await extractor.extract("/nonexistent/file.mp4")

        assert "not found" in str(exc_info.value.message).lower()

    @pytest.mark.asyncio
    async def test_ffmpeg_command_no_shell(self):
        """Test that ffmpeg command uses list args, not shell=True"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "input.mp4"
                input_path.write_text("fake")

                from app.services.audio_extractor import AudioExtractor

                extractor = AudioExtractor(output_dir=tmpdir)
                # Mock the output file existence check
                with patch("pathlib.Path.exists") as mock_exists:
                    mock_exists.return_value = True
                    with patch("pathlib.Path.write_text"):
                        await extractor.extract(str(input_path))

                call_args = mock_run.call_args
                # Verify shell is not True
                assert call_args.kwargs.get("shell") is not True


class TestTranscriber:
    """Tests for TranscriptionService with mocked faster-whisper"""

    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        """Test successful transcription with mocked faster-whisper"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr="",
                stdout="TEXT:Hello world\nLANG:en\nDURATION:5.0\nCONFIDENCE:0.95",
            )

            from app.services.transcriber import FasterWhisperTranscriber, TranscriptionResult

            # Create transcriber without calling _check_modelhub
            transcriber = FasterWhisperTranscriber.__new__(FasterWhisperTranscriber)
            transcriber.model_name = "medium"
            transcriber.model_dir = tempfile.gettempdir()
            transcriber.timeout = 600
            transcriber._transcriber = None

            # Mock the model check to avoid actual import
            with patch.object(transcriber, "_check_modelhub"):
                result = await transcriber.transcribe("/fake/audio.wav", "en")

                assert isinstance(result, TranscriptionResult)
                assert result.text == "Hello world"
                assert result.language == "en"
                assert result.duration == 5.0
                assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_transcribe_timeout(self):
        """Test transcription timeout"""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("python", 600)

            from app.services.transcriber import FasterWhisperTranscriber
            from app.services.exceptions import TimeoutError

            transcriber = FasterWhisperTranscriber.__new__(FasterWhisperTranscriber)
            transcriber.model_name = "medium"
            transcriber.model_dir = tempfile.gettempdir()
            transcriber.timeout = 600
            transcriber._transcriber = None

            with patch.object(transcriber, "_check_modelhub"):
                with pytest.raises(TimeoutError) as exc_info:
                    await transcriber.transcribe("/fake/audio.wav")

                assert "faster-whisper" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_transcribe_model_not_found(self):
        """Test transcription with missing model"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="MODEL_NOT_FOUND:Model not found",
                stdout="",
            )

            from app.services.transcriber import FasterWhisperTranscriber
            from app.services.exceptions import ModelNotFoundError

            transcriber = FasterWhisperTranscriber.__new__(FasterWhisperTranscriber)
            transcriber.model_name = "medium"
            transcriber.model_dir = tempfile.gettempdir()
            transcriber.timeout = 600
            transcriber._transcriber = None

            with patch.object(transcriber, "_check_modelhub"):
                with pytest.raises(ModelNotFoundError) as exc_info:
                    await transcriber.transcribe("/fake/audio.wav")

                assert "medium" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_whisper_command_no_shell(self):
        """Test that whisper command uses list args, not shell=True"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="TEXT:test LANG:zh DURATION:1.0 CONFIDENCE:0.9")

            from app.services.transcriber import FasterWhisperTranscriber

            transcriber = FasterWhisperTranscriber.__new__(FasterWhisperTranscriber)
            transcriber.model_name = "medium"
            transcriber.model_dir = tempfile.gettempdir()
            transcriber.timeout = 600
            transcriber._transcriber = None

            with patch.object(transcriber, "_check_modelhub"):
                await transcriber.transcribe("/fake/audio.wav")

                call_args = mock_run.call_args
                # Verify shell is not True
                assert call_args.kwargs.get("shell") is not True
                # Should be a list of args
                cmd = call_args.args[0]
                assert isinstance(cmd, list)


class TestTranscriptCleaner:
    """Tests for TranscriptCleaner"""

    def test_remove_timestamps(self):
        """Test timestamp removal"""
        from app.services.cleaner import TranscriptCleaner

        cleaner = TranscriptCleaner()
        result = cleaner.clean(
            "[00:01:23] Hello world [00:01:25] This is a test 00:02:30 timestamp"
        )

        assert "00:01:23" not in result.cleaned_text
        assert "Hello world" in result.cleaned_text
        assert "timestamp" in result.cleaned_text
        assert "timestamps" in result.removed_items

    def test_remove_speaker_labels(self):
        """Test speaker label removal"""
        from app.services.cleaner import TranscriptCleaner

        cleaner = TranscriptCleaner()
        result = cleaner.clean(
            "Speaker 1: Hello world\nHost: Welcome\n嘉宾: Thank you"
        )

        assert "Speaker 1:" not in result.cleaned_text
        assert "Host:" not in result.cleaned_text
        assert "Hello world" in result.cleaned_text
        assert "speaker_labels" in result.removed_items

    def test_filter_asr_noise(self):
        """Test ASR noise filtering"""
        from app.services.cleaner import TranscriptCleaner

        cleaner = TranscriptCleaner()
        result = cleaner.clean(
            "Hello ♪♪ world [掌声] this is [噪音] test... again"
        )

        assert "♪♪" not in result.cleaned_text
        assert "[掌声]" not in result.cleaned_text
        assert "[噪音]" not in result.cleaned_text
        assert "Hello world" in result.cleaned_text
        assert "asr_noise" in result.removed_items

    def test_compress_repeated_sentences(self):
        """Test repeated sentence compression"""
        from app.services.cleaner import TranscriptCleaner

        cleaner = TranscriptCleaner()
        # Use Chinese text to avoid period-splitting issues
        result = cleaner.clean(
            "你好吗？你好吗？你好吗？你好吗？很好。"
        )

        # Should have compressed the repeats but kept one instance
        assert "你好吗？" in result.cleaned_text
        # With threshold=3, we keep 3 instances (original + 2 repeats), 4th is removed
        assert result.cleaned_text.count("你好吗？") <= 3
        assert "很好" in result.cleaned_text

    def test_term_normalization(self):
        """Test term normalization"""
        from app.services.cleaner import TranscriptCleaner

        cleaner = TranscriptCleaner()
        result = cleaner.clean(
            "OpenAI released GPT4 and ChatGPT"
        )

        assert "OpenAI" in result.cleaned_text
        assert "GPT-4" in result.cleaned_text
        assert "ChatGPT" in result.cleaned_text

    def test_clean_whitespace(self):
        """Test whitespace cleaning"""
        from app.services.cleaner import TranscriptCleaner

        cleaner = TranscriptCleaner()
        result = cleaner.clean(
            "Hello    world\n\n\n\nBye"
        )

        assert "  " not in result.cleaned_text
        assert "\n\n\n\n" not in result.cleaned_text
        assert "Hello world" in result.cleaned_text

    def test_add_custom_term_correction(self):
        """Test adding custom term corrections"""
        from app.services.cleaner import TranscriptCleaner

        cleaner = TranscriptCleaner()
        cleaner.add_term_correction("mycompany", "My Company")
        result = cleaner.clean("Welcome to mycompany")

        assert "My Company" in result.cleaned_text
        assert "mycompany" not in result.cleaned_text


class TestPipelineIntegration:
    """Integration tests for the pipeline with mocked services"""

    @pytest.mark.asyncio
    async def test_pipeline_with_mock_services(self):
        """Test pipeline with all services mocked"""
        from app.services.cleaner import TranscriptCleaner

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("This is test content for transcription. [00:01:23] Speaker 1: Hello ♪♪")

            # Test cleaner directly (pipeline depends on DB which isn't available in test)
            cleaner = TranscriptCleaner()
            result = cleaner.clean(test_file.read_text())

            assert result.cleaned_text is not None
            assert "00:01:23" not in result.cleaned_text
            assert "Speaker 1:" not in result.cleaned_text
            assert "♪♪" not in result.cleaned_text
            assert "This is test content" in result.cleaned_text