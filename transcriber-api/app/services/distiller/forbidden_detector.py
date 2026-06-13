"""
Forbidden content detector

Detects phrases that indicate summary/abstract mode output.
"""
import re
from typing import List, Tuple

from app.services.distiller.types import QualityIssue


# Forbidden patterns that indicate summary mode
FORBIDDEN_PATTERNS = [
    # Core points / summary phrases
    (r'核心观点', "summary_mode", "包含'核心观点'，违反非摘要原则"),
    (r'核心要点', "summary_mode", "包含'核心要点'，违反非摘要原则"),
    (r'关键结论', "summary_mode", "包含'关键结论'，违反非摘要原则"),
    (r'一句话总结', "summary_mode", "包含'一句话总结'，违反非摘要原则"),
    (r'总结起来', "summary_mode", "包含'总结起来'，违反非摘要原则"),
    (r'要点如下', "summary_mode", "包含'要点如下'，违反非摘要原则"),
    (r'总结：', "summary_mode", "包含'总结：'，违反非摘要原则"),
    (r'^总结$', "summary_mode", "包含'总结'作为标题，违反非摘要原则"),
    (r'^概要$', "summary_mode", "包含'概要'作为标题，违反非摘要原则"),
    (r'^概述$', "summary_mode", "包含'概述'作为标题，违反非摘要原则"),

    # Takeaways / key points
    (r'takeaways', "summary_mode", "包含'takeaways'，违反非摘要原则"),
    (r'划重点', "summary_mode", "包含'划重点'，违反非摘要原则"),
    (r'考点', "summary_mode", "包含'考点'，违反非摘要原则"),
    (r'必背', "summary_mode", "包含'必背'，违反非摘要原则"),
    (r'启发：', "summary_mode", "包含'启发：'，违反非摘要原则"),
    (r'启发如下', "summary_mode", "包含'启发如下'，违反非摘要原则"),
    (r'结论：', "summary_mode", "包含'结论：'，违反非摘要原则"),
    (r'结论如下', "summary_mode", "包含'结论如下'，违反非摘要原则"),

    # Trash titles
    (r'^#+\s*其他', "trash_title", "包含'其他'开头的标题，违反非摘要原则"),
    (r'^#+\s*补充', "trash_title", "包含'补充'开头的标题，违反非摘要原则"),
    (r'^#+\s*Misc', "trash_title", "包含'Misc'标题，违反非摘要原则"),
    (r'^#+\s*杂项', "trash_title", "包含'杂项'标题，违反非摘要原则"),
    (r'其他有效观点', "trash_title", "包含'其他有效观点'，违反非摘要原则"),
    (r'补充说明', "trash_title", "包含'补充说明'，违反非摘要原则"),
    (r'其他观点', "trash_title", "包含'其他观点'，违反非摘要原则"),
    (r'其他内容', "trash_title", "包含'其他内容'，违反非摘要原则"),
    (r'其他信息', "trash_title", "包含'其他信息'，违反非摘要原则"),
]


class ForbiddenDetector:
    """
    Detects forbidden content patterns in distilled text.

    Patterns checked:
    - Summary mode phrases (核心观点, 一句话总结, etc.)
    - Trash titles (其他, 补充, Misc, etc.)
    - Takeaways and key point markers
    """

    def __init__(self):
        self.patterns = FORBIDDEN_PATTERNS

    def detect(self, text: str) -> List[QualityIssue]:
        """
        Detect forbidden patterns in text.

        Args:
            text: Distilled text to check

        Returns:
            List of QualityIssue for each detected pattern
        """
        issues = []
        lines = text.split('\n')

        for pattern, category, description in self.patterns:
            regex = re.compile(pattern, re.MULTILINE | re.IGNORECASE)

            # Check full text for the pattern
            matches = list(regex.finditer(text))

            for match in matches:
                # Determine location
                # Find which line the match is on
                line_num = text[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                # Clean up the line for display
                location = f"第{line_num}行"

                issues.append(QualityIssue(
                    severity="error",
                    category=category,
                    location=location,
                    description=description,
                    suggestion=f"删除包含'{match.group()}'的段落或标题",
                ))

        return issues

    def has_forbidden_content(self, text: str) -> bool:
        """Quick check if text contains any forbidden content"""
        for pattern, _, _ in self.patterns:
            if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                return True
        return False


def detect_forbidden(text: str) -> List[QualityIssue]:
    """
    Convenience function to detect forbidden content.

    Args:
        text: Text to check

    Returns:
        List of QualityIssues found
    """
    detector = ForbiddenDetector()
    return detector.detect(text)