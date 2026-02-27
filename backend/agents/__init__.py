from .base_agent import BaseAgent
from .reader_agent import ReaderAgent
from .searcher_agent import SearcherAgent
# from .verifier_agent import VerifierAgent
# from .writer_agent import WriterAgent

AGENT_REGISTRY = {
    "reader": ReaderAgent,
    "searcher": SearcherAgent,
    # "verifier": VerifierAgent,
    # "writer": WriterAgent,
}

__all__ = [
    "BaseAgent",
    "ReaderAgent",
    "SearcherAgent",
    # "VerifierAgent",
    # "WriterAgent",
    "AGENT_REGISTRY",
]
