"""
Evaluation Models
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class IssueSeverity(Enum):
    """Severity level of documentation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Issue:
    """Documentation issue found during verification"""
    component_id: str
    severity: IssueSeverity
    category: str  # e.g., "missing_param", "incorrect_type", "unclear_description"
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'component_id': self.component_id,
            'severity': self.severity.value,
            'category': self.category,
            'message': self.message,
            'location': self.location,
            'suggestion': self.suggestion,
        }

@dataclass
class MetricScore:
    """Score for a specific metric"""
    name: str
    score: float  # 0-100
    weight: float  # 0-1
    details: Dict[str, Any] = field(default_factory=dict)
    sub_scores: Dict[str, float] = field(default_factory=dict)
    
    def weighted_score(self) -> float:
        """Calculate weighted score"""
        return self.score * self.weight
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'score': self.score,
            'weight': self.weight,
            'weighted_score': self.weighted_score(),
            'details': self.details,
            'sub_scores': self.sub_scores,
        }

@dataclass
class EvaluationResult:
    """Complete evaluation result for documentation"""
    
    # Overall scores
    overall_score: float  # Weighted average 0-100
    grade: str = ""  # A, B, C, D, F
    
    # Metric scores
    completeness: MetricScore = None
    accuracy: MetricScore = None
    clarity: MetricScore = None
    consistency: MetricScore = None
    
    # Issues found
    issues: List[Issue] = field(default_factory=list)
    
    # Component-level results
    component_scores: Dict[str, float] = field(default_factory=dict)
    # {component_id: score}
    
    # Statistics
    total_components: int = 0
    documented_components: int = 0
    components_with_issues: int = 0
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    # Metadata
    evaluated_at: datetime = field(default_factory=datetime.now)
    evaluator_version: str = "1.0.0"
    
    def __post_init__(self):
        """Calculate grade after initialization"""
        if not self.grade:
            self.grade = self._calculate_grade()
    
    def _calculate_grade(self) -> str:
        """Calculate letter grade from overall score"""
        if self.overall_score >= 90:
            return "A"
        elif self.overall_score >= 80:
            return "B"
        elif self.overall_score >= 70:
            return "C"
        elif self.overall_score >= 60:
            return "D"
        else:
            return "F"
    
    def get_issues_by_severity(self, severity: IssueSeverity) -> List[Issue]:
        """Get issues filtered by severity"""
        return [issue for issue in self.issues if issue.severity == severity]
    
    def coverage_percentage(self) -> float:
        """Calculate documentation coverage percentage"""
        if self.total_components == 0:
            return 0.0
        return (self.documented_components / self.total_components) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'overall_score': self.overall_score,
            'grade': self.grade,
            'metrics': {
                'completeness': self.completeness.to_dict() if self.completeness else None,
                'accuracy': self.accuracy.to_dict() if self.accuracy else None,
                'clarity': self.clarity.to_dict() if self.clarity else None,
                'consistency': self.consistency.to_dict() if self.consistency else None,
            },
            'issues': [issue.to_dict() for issue in self.issues],
            'component_scores': self.component_scores,
            'statistics': {
                'total_components': self.total_components,
                'documented_components': self.documented_components,
                'coverage_percentage': self.coverage_percentage(),
                'components_with_issues': self.components_with_issues,
            },
            'recommendations': self.recommendations,
            'evaluated_at': self.evaluated_at.isoformat(),
            'evaluator_version': self.evaluator_version,
        }