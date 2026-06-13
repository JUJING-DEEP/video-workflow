"""
Quality checker for distilled text

Checks multiple dimensions:
- forbidden_content: No summary mode patterns
- structure: No bullet abuse, preserved paragraphs
- titles: No trash titles
"""
import re
from typing import List

from app.services.distiller.types import QualityIssue
from app.services.distiller.forbidden_detector import ForbiddenDetector, FORBIDDEN_PATTERNS


class QualityChecker:
    """
    Multi-dimensional quality checker for distilled text.

    Checks performed:
    1. forbidden_content - No summary mode patterns
    2. bullet_abuse - Bullet points ratio under threshold
    3. paragraph_integrity - Average paragraph length acceptable
    4. structure_preserved - Full paragraphs preserved (not compressed)
    """

    BULLET_RATIO_THRESHOLD = 0.15  # 15% of lines can be bullets
    MIN_PARAGRAPH_LENGTH = 30  # Minimum characters for a paragraph

    def __init__(self):
        self.forbidden_detector = ForbiddenDetector()

    def check(self, text: str) -> tuple[bool, List[QualityIssue]]:
        """
        Run all quality checks on distilled text.

        Args:
            text: Distilled text to check

        Returns:
            Tuple of (passed, issues)
        """
        issues = []

        # Check 1: Forbidden content
        issues.extend(self._check_forbidden(text))

        # Check 2: Bullet abuse
        issues.extend(self._check_bullet_abuse(text))

        # Check 3: Paragraph integrity
        issues.extend(self._check_paragraph_integrity(text))

        # Check 4: Structure preserved (no compression to bullet points)
        issues.extend(self._check_structure_preserved(text))

        passed = all(issue.severity == "warning" or issue.category == "structure_warning"
                     for issue in issues)

        # Strict pass: no errors
        has_errors = any(issue.severity == "error" for issue in issues)
        passed = not has_errors

        return passed, issues

    def _check_forbidden(self, text: str) -> List[QualityIssue]:
        """Check for forbidden content patterns"""
        return self.forbidden_detector.detect(text)

    def _check_bullet_abuse(self, text: str) -> List[QualityIssue]:
        """Check bullet points ratio is under threshold"""
        lines = text.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        bullet_lines = [l for l in non_empty_lines if l.strip().startswith(('-', '*', '•'))]

        if not non_empty_lines:
            return []

        ratio = len(bullet_lines) / len(non_empty_lines)

        if ratio > self.BULLET_RATIO_THRESHOLD:
            return [QualityIssue(
                severity="error",
                category="bullet_abuse",
                location="全文",
                description=f"bullet points 比例过高 ({ratio:.1%})，违反非摘要原则",
                suggestion="将 bullet points 扩展为完整段落",
            )]

        return []

    def _check_paragraph_integrity(self, text: str) -> List[QualityIssue]:
        """
        Check that paragraphs have sufficient length.

        A paragraph is content between headings or blank lines.
        """
        issues = []

        # Split into paragraphs (content between headings or blank lines)
        paragraphs = re.split(r'\n(?=#)', text)

        short_paragraphs = 0
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # Skip headings
            if para.startswith('#'):
                continue
            if len(para) < self.MIN_PARAGRAPH_LENGTH:
                short_paragraphs += 1

        total_paragraphs = len([p for p in paragraphs if p.strip() and not p.startswith('#')])
        if total_paragraphs > 0 and short_paragraphs / total_paragraphs > 0.3:
            issues.append(QualityIssue(
                severity="warning",
                category="paragraph_fragmentation",
                location="全文",
                description=f"短段落过多 ({short_paragraphs}/{total_paragraphs})，可能影响可读性",
                suggestion="合并相邻短段落",
            ))

        return issues

    def _check_structure_preserved(self, text: str) -> List[QualityIssue]:
        """
        Check that content is structured as full paragraphs, not compressed points.

        Warning only (not error) since some legitimate uses of bullets exist.
        """
        lines = text.split('\n')

        # Count lines that look like compressed points vs full sentences
        point_like_lines = 0
        full_sentence_lines = 0

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            # Short lines that don't end with proper punctuation might be bullet points
            if len(stripped) < 40 and not stripped.endswith(('。', '！', '？', '"', '"')):
                point_like_lines += 1
            else:
                full_sentence_lines += 1

        total = point_like_lines + full_sentence_lines
        if total > 0 and point_like_lines / total > 0.4:
            return [QualityIssue(
                severity="warning",
                category="structure_warning",
                location="全文",
                description=f"短句/要点式内容比例较高 ({point_like_lines}/{total})，可能违反非摘要原则",
                suggestion="将要点扩展为完整段落",
            )]

        return []


def quality_check(text: str) -> tuple[bool, List[QualityIssue]]:
    """
    Convenience function to run quality checks.

    Args:
        text: Distilled text to check

    Returns:
        Tuple of (passed, issues)
    """
    checker = QualityChecker()
    return checker.check(text)