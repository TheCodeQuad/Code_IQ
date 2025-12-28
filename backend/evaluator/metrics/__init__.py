from .accuracy import AccuracyMetric
from .clarity import ClarityMetric
from .completeness import CompletenessMetric
from .consistency import ConsistencyMetric

METRICS = [
    AccuracyMetric(),
    ClarityMetric(),
    CompletenessMetric(),
    ConsistencyMetric(),
]

__all__ = ["METRICS"]
