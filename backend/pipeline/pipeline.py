# backend/pipeline/pipeline.py
"""
Main pipeline orchestrator
"""
from backend.core.repository_parser import RepositoryParser
from backend.pipeline.navigator_adapter import NavigatorAdapter
from backend.agents.orchestrator.orchestrator import Orchestrator
from backend.evaluator.evaluator import Evaluator

class DocumentationPipeline:
    def run(self, repo_path):
        # Stage 1: Navigator
        ir, dag = self.navigator.parse(repo_path)
        
        # Stage 2: Adapt
        components = self.adapter.transform(ir, dag)
        
        # Stage 3: Multi-Agent
        documented = self.orchestrator.process(components)
        
        # Stage 4: Evaluator
        output = self.evaluator.evaluate(documented)
        
        return output