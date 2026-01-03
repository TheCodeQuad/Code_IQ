"""
Shared data models across all modules
"""
from .code_component import CodeComponent, ComponentType, Location
from .documentation import Documentation, DocSection, Example
from .metadata import Metadata, FileMetadata, ComponentMetadata
from .evaluation import EvaluationResult, MetricScore, Issue, IssueSeverity

__all__ = [
    'CodeComponent',
    'ComponentType',
    'Location',
    'Documentation',
    'DocSection',
    'Example',
    'Metadata',
    'FileMetadata',
    'ComponentMetadata',
    'EvaluationResult',
    'MetricScore',
    'Issue',
    'IssueSeverity',
]