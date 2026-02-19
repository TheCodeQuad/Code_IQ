"""
Shared data models across all modules
"""
from .code_component import CodeComponent, ComponentType, Location
from .documentation import Documentation, DocSection, Example
from .evaluation import EvaluationResult, MetricScore, Issue, IssueSeverity

__all__ = [
    'CodeComponent',
    'ComponentType',
    'Location',
    'Documentation',
    'DocSection',
    'Example',
    'EvaluationResult',
    'MetricScore',
    'Issue',
    'IssueSeverity',
]