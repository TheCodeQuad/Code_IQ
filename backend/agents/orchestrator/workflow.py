"""
Workflow Manager
Manages agent execution workflow
"""
from typing import List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from backend.utils.logger import get_logger

logger = get_logger(__name__)

class WorkflowStage(Enum):
    """Workflow stages"""
    READ = "read"
    SEARCH = "search"
    WRITE = "write"
    VERIFY = "verify"

@dataclass
class WorkflowStep:
    """Single workflow step"""
    stage: WorkflowStage
    agent_name: str
    required: bool = True
    retry_on_failure: bool = True
    depends_on: List[WorkflowStage] = None

class WorkflowManager:
    """Manages the workflow of agents"""
    
    def __init__(self):
        self.logger = get_logger("workflow")
        self.workflow = self._create_default_workflow()
    
    def _create_default_workflow(self) -> List[WorkflowStep]:
        """Create default workflow"""
        return [
            WorkflowStep(
                stage=WorkflowStage.READ,
                agent_name="reader",
                required=True,
                retry_on_failure=True
            ),
            WorkflowStep(
                stage=WorkflowStage.SEARCH,
                agent_name="searcher",
                required=False,
                retry_on_failure=False,
                depends_on=[WorkflowStage.READ]
            ),
            WorkflowStep(
                stage=WorkflowStage.WRITE,
                agent_name="writer",
                required=True,
                retry_on_failure=True,
                depends_on=[WorkflowStage.READ, WorkflowStage.SEARCH]
            ),
            WorkflowStep(
                stage=WorkflowStage.VERIFY,
                agent_name="verifier",
                required=False,
                retry_on_failure=True,
                depends_on=[WorkflowStage.WRITE]
            )
        ]
    
    def get_next_stage(self, current_stage: WorkflowStage) -> WorkflowStage:
        """Get next workflow stage"""
        stages = [step.stage for step in self.workflow]
        current_idx = stages.index(current_stage)
        
        if current_idx < len(stages) - 1:
            return stages[current_idx + 1]
        
        return None
    
    def is_stage_required(self, stage: WorkflowStage) -> bool:
        """Check if stage is required"""
        for step in self.workflow:
            if step.stage == stage:
                return step.required
        return False