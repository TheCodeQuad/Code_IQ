# evaluator/base.py

class BaseEvaluator:
    """
    Abstract base class for all evaluators.

    Attributes:
        name (str): Name of the evaluator.
        description (str): Description of what this evaluator does.
        score (float): The evaluation score from 0 to 1.
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.score: float = 0.0

    def evaluate(self, *args, **kwargs) -> float:
        raise NotImplementedError("Subclasses must implement evaluate()")