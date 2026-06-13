"""
Transcript Cleaning Service

Cleans ASR transcripts by removing:
- Timestamps
- Speaker labels
- Repetition
- Verbal fillers and ASR noise
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.services.exceptions import MediaProcessingError


@dataclass
class CleaningResult:
    """Result from transcript cleaning"""

    cleaned_text: str
    removed_items: List[str] = field(default_factory=list)
    corrections: Dict[str, str] = field(default_factory=dict)


class TranscriptCleaner:
    """
    Transcript cleaning engine.

    Removes timestamps, speaker labels, ASR noise, repetition,
    and verbal fillers while preserving content.
    """

    # Timestamp patterns
    TIMESTAMP_PATTERNS = [
        r'\[\d{2}:\d{2}:\d{2}\]',  # [00:01:23]
        r'\d{2}:\d{2}:\d{2}\s*-->\s*\d{2}:\d{2}:\d{2}',  # 00:01:23 --> 00:01:25
        r'(?<!\w)\d{2}:\d{2}:\d{2}(?!\w)',  # 00:01:23 standalone
        r'[\（\(]?\d{1,2}分\d{1,2}秒[\)\)]?',  # (1分23秒)
        r'第\d+分钟',  # 第3分钟
    ]

    # Speaker label patterns
    SPEAKER_PATTERNS = [
        r'Speaker\s*\d+[:：]?',
        r'Host\s*\d+[:：]?',
        r'Guest\s*\d+[:：]?',
        r'Narrator[:：]?',
        r'VO[:：]?\s*',
        r'说话人[A-Za-z\d]+[:：]?',
        r'主持人[:：]?',
        r'嘉宾[:：]?',
        r'听众[:：]?',
        r'观众[:：]?',
        r'主讲人[:：]?',
        r'讲师[:：]?',
        r'专家[:：]?',
        r'[A-Za-z一-龥]+[:：]\s*',  # Generic "Name:" pattern
    ]

    # ASR noise patterns
    ASR_NOISE_PATTERNS = [
        r'♪+',  # Music notes
        r'♫+',
        r'𝄞+',
        r'\.{3,}',  # Ellipsis
        r'-{3,}',  # Dashes
        r'_{3,}',  # Underscores
        r'\*{3,}',  # Asterisks
        r'\[噪音\]',
        r'\[掌声\]',
        r'\[笑声\]',
        r'\[咳嗽\]',
        r'\[沉默\]',
        r'\[音乐\]',
        r'\[旁白\]',
        r'\(unk\)',
        r'\(silence\)',
        r'\(cough\)',
        r'\(lipsmack\)',
        r'[🔊🎵🎶]+',  # Emojis
    ]

    # Verbal fillers to remove
    VERBAL_FILLERS = [
        r'\b嗯+\b',
        r'\b啊+\b',
        r'\b这个那个\b',
        r'\b就是说\b',
        r'\b然后\b',
        r'\b其实\b',
        r'\b可能\b(?=\s*[,，；;])',  # "可能," at clause start
        r'\b我觉得\b(?=\s*[,，；;])',  # "我觉得," at clause start
        r'\b你知道\b',
        r'\b对吧\b',
        r'\b是吧\b',
        r'\b差不多\b',
    ]

    # Term corrections (company names, product names, etc.)
    TERM_CORRECTIONS = {
        # Companies
        "openai": "OpenAI",
        "google": "Google",
        "microsoft": "Microsoft",
        "apple": "Apple",
        "amazon": "Amazon",
        "meta": "Meta",
        "bytedance": "字节跳动",
        "字节": "字节跳动",
        "腾讯": "腾讯",
        "阿里": "阿里巴巴",
        "alibaba": "阿里巴巴",
        "nvidia": "NVIDIA",
        # Products
        "gpt4": "GPT-4",
        "gpt 4": "GPT-4",
        "chatgpt": "ChatGPT",
        "gpt-3.5": "GPT-3.5",
        "claude 2": "Claude 2",
        "claude2": "Claude 2",
        "claude3": "Claude 3",
        "claude 3": "Claude 3",
        # Technical Terms
        "ai": "AI",
        "llm": "LLM",
        "rag": "RAG",
        "api": "API",
        "ml": "ML",
        "nlp": "NLP",
        "gpu": "GPU",
    }

    def __init__(self, custom_term_corrections: Optional[Dict[str, str]] = None):
        """
        Initialize cleaner.

        Args:
            custom_term_corrections: Additional term corrections to apply
        """
        self.term_corrections = dict(self.TERM_CORRECTIONS)
        if custom_term_corrections:
            self.term_corrections.update(custom_term_corrections)

    def clean(self, raw_text: str) -> CleaningResult:
        """
        Clean transcript text.

        Args:
            raw_text: Raw transcript text from ASR

        Returns:
            CleaningResult with cleaned text and metadata
        """
        text = raw_text
        removed_items: List[str] = []
        corrections: Dict[str, str] = {}

        original_len = len(text)

        # Step 1: Remove timestamps
        text = self._remove_timestamps(text)
        if len(text) < original_len:
            removed_items.append("timestamps")
            original_len = len(text)

        # Step 2: Remove speaker labels
        text = self._remove_speaker_labels(text)
        if len(text) < original_len:
            removed_items.append("speaker_labels")
            original_len = len(text)

        # Step 3: Filter ASR noise
        text = self._filter_asr_noise(text)
        if len(text) < original_len:
            removed_items.append("asr_noise")
            original_len = len(text)

        # Step 4: Remove verbal fillers
        text = self._remove_verbal_fillers(text)
        if len(text) < original_len:
            removed_items.append("verbal_fillers")
            original_len = len(text)

        # Step 5: Compress repeated sentences
        text = self._compress_repeated_sentences(text)
        if len(text) < original_len:
            removed_items.append("repeated_sentences")
            original_len = len(text)

        # Step 6: Normalize terms
        text, applied_corrections = self._normalize_terms(text)
        corrections.update(applied_corrections)

        # Step 7: Clean whitespace
        text = self._clean_whitespace(text)

        return CleaningResult(
            cleaned_text=text.strip(),
            removed_items=removed_items,
            corrections=corrections,
        )

    def _remove_timestamps(self, text: str) -> str:
        """Remove timestamp patterns"""
        for pattern in self.TIMESTAMP_PATTERNS:
            text = re.sub(pattern, '', text)
        return text

    def _remove_speaker_labels(self, text: str) -> str:
        """Remove speaker label patterns"""
        for pattern in self.SPEAKER_PATTERNS:
            text = re.sub(pattern, '', text)
        return text

    def _filter_asr_noise(self, text: str) -> str:
        """Filter ASR noise patterns"""
        for pattern in self.ASR_NOISE_PATTERNS:
            text = re.sub(pattern, '', text)
        return text

    def _remove_verbal_fillers(self, text: str) -> str:
        """Remove verbal filler patterns"""
        for pattern in self.VERBAL_FILLERS:
            text = re.sub(pattern, '', text)
        return text

    def _compress_repeated_sentences(self, text: str, threshold: int = 3) -> str:
        """Compress consecutive repeated sentences"""
        import re

        # Split text by sentence separators (Chinese and English punctuation)
        # Capture content + trailing punctuation as one unit
        sentence_pattern = r'([^。！？.?!\n]+)([。！？.?!\n]?)'

        sentences = re.findall(sentence_pattern, text)

        if not sentences:
            return text

        result = []
        prev_content = None
        repeat_count = 0

        for content, punct in sentences:
            content = content.strip()
            if not content:
                continue

            # Skip very short content (likely just punctuation)
            if len(content) <= 1:
                result.append(content + punct)
                continue

            # Check for repetition (only meaningful for content > 2 chars)
            if len(content) > 2 and content == prev_content:
                repeat_count += 1
                if repeat_count >= threshold:
                    continue  # Skip this repeated sentence
            else:
                repeat_count = 0
                prev_content = content

            result.append(content + punct)

        return ''.join(result)

    def _normalize_terms(self, text: str) -> tuple:
        """Normalize terms and track corrections"""
        applied = {}
        for wrong, correct in self.term_corrections.items():
            pattern = r'\b' + re.escape(wrong) + r'\b'
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            if matches:
                text = re.sub(pattern, correct, text, flags=re.IGNORECASE)
                for match in matches:
                    applied[match.lower()] = correct
        return text, applied

    def _clean_whitespace(self, text: str) -> str:
        """Clean extra whitespace"""
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = '\n'.join(line.strip() for line in text.split('\n'))
        return text

    def add_term_correction(self, wrong: str, correct: str) -> None:
        """Add a custom term correction"""
        self.term_corrections[wrong] = correct