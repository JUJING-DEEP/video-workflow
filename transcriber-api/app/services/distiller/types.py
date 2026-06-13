"""Distiller types"""
from dataclasses import dataclass, field
from typing import List, Literal, Optional


@dataclass
class DistillInput:
    """Input for distillation"""
    cleaned_text: str
    language: str = "zh"
    max_headings: int = 5


@dataclass
class QualityIssue:
    """A quality issue found in distilled text"""
    severity: Literal["error", "warning"]
    category: str
    location: str
    description: str
    suggestion: Optional[str] = None


@dataclass
class DistillResult:
    """Result from distillation"""
    distilled_text: str
    passed: bool
    issues: List[QualityIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    iterations: int = 1