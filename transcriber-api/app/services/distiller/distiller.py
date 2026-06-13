"""
Distiller - Main distillation function

Produces shareable distilled transcripts from cleaned text.
"""
import os
import logging
from typing import Optional

from app.services.distiller.types import DistillInput, DistillResult, QualityIssue
from app.services.distiller.quality_checker import QualityChecker
from app.services.distiller.forbidden_detector import ForbiddenDetector

logger = logging.getLogger(__name__)

# Anthropic API Key
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# System prompt for distillation
SYSTEM_PROMPT = """你是一个专业的文本整理专家，负责将转录文本转化为高质量的可阅读整理稿。

核心原则：
1. 保留原文结构，不是生成摘要
2. 保留完整的判断链（论点→论据→论证）
3. 保留具体的数据、案例、类比、金句
4. 删除寒暄和客套话
5. 按一级/二级标题组织内容

禁止：
- 生成「核心观点」「一句话总结」「启发」「结论」
- 生成要点列表（bullet points）
- 使用「其他」「Misc」「杂项」等分类标题
- 压缩内容为要点

输出格式：
# 一级主题（从内容中提炼）

## 二级主题（描述具体内容）

正文内容，保留完整段落...

标题必须来自内容，不得使用「概述」「背景」等通用标题。"""


USER_PROMPT_TEMPLATE = """请整理以下文本，生成提纯稿：

---

{cleaned_text}

---

要求：
1. 标题必须来自内容，不得使用「概述」「背景」等通用标题
2. 正文必须保留完整段落，不得压缩为要点列表
3. 保留原文中的具体数据、案例、金句
4. 删除所有寒暄和客套话
5. 输出格式为 Markdown，包含一级和二级标题"""


class Distiller:
    """
    Distillation engine that converts cleaned transcript to shareable format.

    Uses LLM (Claude) if API key is available, otherwise returns structured fallback.
    """

    def __init__(self, api_key: Optional[str] = None):
        # Only use env var if no explicit key provided
        if api_key is not None and api_key != "":
            self.api_key = api_key
        elif ANTHROPIC_API_KEY:
            self.api_key = ANTHROPIC_API_KEY
        else:
            self.api_key = None
        self.quality_checker = QualityChecker()
        self.forbidden_detector = ForbiddenDetector()

    def distill(self, cleaned_text: str, language: str = "zh") -> DistillResult:
        """
        Distill cleaned text to shareable format.

        Args:
            cleaned_text: Cleaned transcript text
            language: Language code (default: zh)

        Returns:
            DistillResult with distilled text and quality issues
        """
        warnings = []

        # Check input length
        if len(cleaned_text) < 50:
            return DistillResult(
                distilled_text=cleaned_text,
                passed=False,
                issues=[QualityIssue(
                    severity="error",
                    category="input_too_short",
                    location="输入",
                    description="输入文本过短，无法提纯",
                    suggestion="确保输入文本长度大于 50 字符",
                )],
                warnings=warnings,
            )

        # Generate distillation
        if self.api_key:
            distilled = self._llm_distill(cleaned_text, language)
        else:
            distilled = self._rule_based_distill(cleaned_text)
            warnings.append("使用规则降级提纯，API key 未配置")

        # Quality check
        passed, issues = self.quality_checker.check(distilled)

        return DistillResult(
            distilled_text=distilled,
            passed=passed,
            issues=issues,
            warnings=warnings,
            iterations=1,
        )

    def _llm_distill(self, cleaned_text: str, language: str) -> str:
        """Use LLM for distillation"""
        try:
            import anthropic
        except ImportError:
            raise ValueError("anthropic package not installed, cannot use LLM distillation")

        client = anthropic.Anthropic(api_key=self.api_key)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": USER_PROMPT_TEMPLATE.format(cleaned_text=cleaned_text)
                    }
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.warning(f"LLM distillation failed: {e}, falling back to rule-based")
            return self._rule_based_distill(cleaned_text)

    def _rule_based_distill(self, cleaned_text: str) -> str:
        """
        Rule-based fallback distillation.

        Simple implementation that:
        1. Removes greetings
        2. Groups sentences into paragraphs
        3. Generates basic headings
        """
        text = cleaned_text

        # 1. Remove common greetings
        greetings = [
            "大家好", "谢谢大家", "观众朋友们好", "欢迎收看",
            "今天我们来讨论", "大家好我是", "感谢收听",
        ]
        for g in greetings:
            text = text.replace(g, "")

        # 2. Remove polite phrases
        polite = [
            "这个问题问得好", "好问题", "谢谢你的提问",
            "我们来总结一下", "你问得很好",
        ]
        for p in polite:
            text = text.replace(p, "")

        # 3. Split into sentences and regroup
        sentences = re.split(r'([。！？])', text)
        paragraphs = []
        current_para = []
        char_count = 0

        for i, sent in enumerate(sentences):
            if i % 2 == 0:  # Text part
                sent = sent.strip()
                if not sent:
                    continue
                current_para.append(sent)
                char_count += len(sent)
            else:  # Punctuation part
                if current_para:
                    current_para.append(sent)
                if char_count >= 150 or (i % 4 == 1 and current_para):
                    para_text = "".join(current_para).strip()
                    if para_text:
                        paragraphs.append(para_text)
                    current_para = []
                    char_count = 0

        if current_para:
            paragraphs.append("".join(current_para).strip())

        # 4. Generate basic structure
        result_lines = []
        result_lines.append("# 内容整理\n")

        for i, para in enumerate(paragraphs):
            if i < 3:
                result_lines.append(f"\n## 主题{i + 1}\n")
            else:
                result_lines.append(f"\n## 内容片段\n")
            result_lines.append(f"\n{para}")

        return "".join(result_lines)


def distill_transcript(cleaned_text: str, language: str = "zh") -> DistillResult:
    """
    Main distillation function.

    Args:
        cleaned_text: Cleaned transcript text
        language: Language code (default: zh)

    Returns:
        DistillResult with distilled text and quality issues
    """
    import re

    distiller = Distiller()
    return distiller.distill(cleaned_text, language)