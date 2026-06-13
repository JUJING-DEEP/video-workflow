"""
Tests for distiller module
"""
import os
import pytest

from app.services.distiller.types import DistillInput, DistillResult, QualityIssue
from app.services.distiller.forbidden_detector import ForbiddenDetector, detect_forbidden
from app.services.distiller.quality_checker import QualityChecker, quality_check
from app.services.distiller.distiller import Distiller, distill_transcript


class TestForbiddenDetector:
    """Tests for forbidden content detection"""

    def test_detect_core_points(self):
        """Test detection of '核心观点'"""
        detector = ForbiddenDetector()
        issues = detector.detect("这是内容。核心观点：第一点")

        assert len(issues) == 1
        assert issues[0].category == "summary_mode"
        assert issues[0].severity == "error"

    def test_detect_one_sentence_summary(self):
        """Test detection of '一句话总结' - triggers both pattern and 总结："""
        detector = ForbiddenDetector()
        issues = detector.detect("内容...一句话总结：xxx")

        # Both "一句话总结" and "总结：" patterns match
        assert len(issues) >= 1
        assert any("一句话总结" in i.description for i in issues)

    def test_detect_enlightenment(self):
        """Test detection of '启发'"""
        detector = ForbiddenDetector()
        issues = detector.detect("启发：这个故事告诉我们...")

        assert len(issues) == 1
        assert issues[0].category == "summary_mode"

    def test_detect_conclusion(self):
        """Test detection of '结论'"""
        detector = ForbiddenDetector()
        issues = detector.detect("结论：需要这样做")

        assert len(issues) == 1
        assert issues[0].category == "summary_mode"

    def test_detect_other_viewpoints(self):
        """Test detection of '其他有效观点'"""
        detector = ForbiddenDetector()
        issues = detector.detect("# 其他有效观点\n内容")

        # Matches both #+\s*其他 and 其他有效观点
        assert issues[0].category == "trash_title"

    def test_detect_supplementary_notes(self):
        """Test detection of '补充说明'"""
        detector = ForbiddenDetector()
        issues = detector.detect("## 补充说明\n内容")

        assert len(issues) >= 1
        assert any("补充" in i.description for i in issues)

    def test_detect_trash_title_other(self):
        """Test detection of '其他' heading"""
        detector = ForbiddenDetector()
        # Line starting with '## 其他'
        issues = detector.detect("## 其他\n内容段落")

        assert len(issues) >= 1

    def test_detect_takeaways(self):
        """Test detection of 'takeaways'"""
        detector = ForbiddenDetector()
        issues = detector.detect("Key takeaways: 1. xxx")

        assert len(issues) == 1
        assert issues[0].category == "summary_mode"

    def test_detect_multiple_issues(self):
        """Test detection of multiple forbidden patterns"""
        detector = ForbiddenDetector()
        issues = detector.detect("核心观点：xxx\n一句话总结：yyy\n## 其他\n内容")

        assert len(issues) >= 3

    def test_clean_text_passes(self):
        """Test that clean text passes forbidden detection"""
        detector = ForbiddenDetector()
        issues = detector.detect("# AI Agent 的记忆能力\n\n## 短期记忆实现\n\n本文讨论了...")

        assert len(issues) == 0

    def test_has_forbidden_content(self):
        """Test quick check method"""
        detector = ForbiddenDetector()

        assert detector.has_forbidden_content("核心观点：xxx") is True
        assert detector.has_forbidden_content("这是正常内容") is False

    def test_convenience_function(self):
        """Test detect_forbidden convenience function"""
        issues = detect_forbidden("核心观点：xxx")
        assert len(issues) == 1


class TestQualityChecker:
    """Tests for quality checker"""

    def test_clean_text_passes(self):
        """Test that clean structured text passes"""
        checker = QualityChecker()
        text = "# AI Agent 的记忆能力\n\n## 短期记忆实现\n\n本文讨论了AI Agent如何实现短期记忆能力。\n通过上下文窗口技术，Agent可以在对话过程中保持信息连贯性。\n具体实现包括滑动窗口和注意力机制的应用。\n\n## 长期记忆机制\n\n长期记忆则通过外部存储系统实现。\n向量数据库如ChromaDB被用于存储和检索语义相似的内容。"

        passed, issues = checker.check(text)
        assert passed is True
        assert len(issues) == 0

    def test_forbidden_content_fails(self):
        """Test that text with forbidden content fails"""
        checker = QualityChecker()
        text = "# 核心观点\n\n1. 要点一\n2. 要点二"

        passed, issues = checker.check(text)
        assert passed is False
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) > 0

    def test_bullet_abuse_fails(self):
        """Test that excessive bullet points fail"""
        checker = QualityChecker()
        text = "# 内容\n\n- 第一点\n- 第二点\n- 第三点\n- 第四点\n- 第五点\n- 第六点\n- 第七点"

        passed, issues = checker.check(text)
        bullet_issues = [i for i in issues if i.category == "bullet_abuse"]
        assert len(bullet_issues) == 1

    def test_convenience_function(self):
        """Test quality_check convenience function"""
        passed, issues = quality_check("# 正常内容\n\n段落内容...")
        assert passed is True


class TestDistiller:
    """Tests for distiller"""

    def test_rule_based_distill_short_input(self):
        """Test rule-based distill with short input"""
        # Clear env var to force rule-based
        old_key = None
        try:
            distiller = Distiller(api_key=None)
            result = distiller.distill("短文本")

            assert result.distilled_text is not None
            assert len(result.issues) > 0
            assert result.issues[0].category == "input_too_short"
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    @pytest.mark.skipif(
        bool(os.environ.get("ANTHROPIC_API_KEY")),
        reason="ANTHROPIC_API_KEY is set, cannot test rule-based fallback"
    )
    def test_rule_based_distill(self):
        """Test rule-based distill produces structure"""
        distiller = Distiller()
        text = "这是第一句话。这是第二句话。这是第三句话。" * 20

        result = distiller.distill(text)

        assert "#" in result.distilled_text
        assert "##" in result.distilled_text

    @pytest.mark.skipif(
        bool(os.environ.get("ANTHROPIC_API_KEY")),
        reason="ANTHROPIC_API_KEY is set, cannot test rule-based fallback"
    )
    def test_distill_convenience_function(self):
        """Test distill_transcript convenience function"""
        result = distill_transcript("测试文本内容。" * 30)

        assert isinstance(result, DistillResult)
        assert result.distilled_text is not None


# Golden dataset test cases
GOLDEN_CASES = [
    {
        "name": "core_points_summary",
        "text": "# 核心观点\n\n1. AI Agent 需要记忆能力\n2. 短期记忆通过上下文实现\n3. 长期记忆依赖向量数据库",
        "expected_fail": True,
        "expected_categories": ["summary_mode"],
    },
    {
        "name": "one_sentence_summary",
        "text": "# 视频总结\n\n一句话总结：AI Agent 的记忆能力对其智能化至关重要。\n\n## 主要内容\n\n本文讨论了AI Agent的技术实现。",
        "expected_fail": True,
        "expected_categories": ["summary_mode"],
    },
    {
        "name": "enlightenment_mode",
        "text": "# 内容整理\n\n启发：通过本文学习，我们了解到...\n\n## 详细内容\n\n具体内容见正文。",
        "expected_fail": True,
        "expected_categories": ["summary_mode"],
    },
    {
        "name": "other_viewpoints",
        "text": "# 主要讨论\n\n## 其他有效观点\n\n还有一种观点认为...\n\n## 补充说明\n\n另一些人也认为。",
        "expected_fail": True,
        "expected_categories": ["trash_title", "trash_title"],
    },
    {
        "name": "valid_distilled_content",
        "text": "# AI Agent 的记忆能力实现方式\n\n## 短期记忆：上下文窗口技术\n\nAI Agent 通过上下文窗口技术实现短期记忆。在对话过程中，\n系统会维护一个滑动窗口，将最近的对话内容保留在内存中。\n这种方式使得Agent能够理解当前对话的上下文。\n\n## 长期记忆：向量数据库\n\n对于需要跨会话保持的知识，Agent使用外部向量数据库存储。\n遇到重要信息时，系统会将内容转换为向量并存储。\n检索时，通过语义相似度匹配找到相关内容。",
        "expected_fail": False,
        "expected_categories": [],
    },
]


class TestGoldenDataset:
    """Golden dataset tests - 5 real-world cases"""

    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["name"] for c in GOLDEN_CASES])
    def test_golden_cases(self, case):
        """Test golden dataset cases"""
        detector = ForbiddenDetector()
        checker = QualityChecker()

        # Check forbidden detection
        forbidden_issues = detector.detect(case["text"])

        # Check quality
        passed, quality_issues = checker.check(case["text"])

        if case["expected_fail"]:
            # Problematic content should have issues
            all_issues = forbidden_issues + quality_issues
            found_categories = set(i.category for i in all_issues if i.severity == "error")

            for expected in case["expected_categories"]:
                assert expected in found_categories, \
                    f"Case {case['name']}: expected category '{expected}' not found in {found_categories}"
        else:
            # Clean content should pass
            assert len(forbidden_issues) == 0, \
                f"Case {case['name']}: unexpected forbidden issues: {forbidden_issues}"
            assert passed is True, \
                f"Case {case['name']}: clean content should pass quality check"