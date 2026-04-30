"""
Base Agent Class
All agents inherit from this base class
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.utils.logger import get_logger
from backend.utils.llm_client import get_llm_client, LLMRequest
from backend.utils.config_handler import get_config
from backend.models.code_component import CodeComponent

logger = get_logger(__name__)

class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class AgentContext:
    """Context passed between agents"""
    component: CodeComponent
    previous_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_result(self, agent_name: str, result: Any):
        """Add result from an agent"""
        self.previous_results[agent_name] = result
    
    def get_result(self, agent_name: str) -> Optional[Any]:
        """Get result from a previous agent"""
        return self.previous_results.get(agent_name)

@dataclass
class AgentResult:
    """Result from agent execution"""
    agent_name: str
    status: AgentStatus
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        """Check if execution was successful"""
        return self.status == AgentStatus.SUCCESS

class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.config = get_config()
        self.llm_client = get_llm_client()
        self.logger = get_logger(f"agent.{agent_name}")
        
        # Load agent-specific configuration
        self.agent_config = self.config.get(f'agents.{agent_name}', {})
        
        # Execution statistics
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_execution_time = 0.0
        
        # Conversation memory for LLM interactions
        self.memory: List[Dict[str, str]] = []
        
        self.logger.info(f"Initialized {agent_name} agent")
    
    @abstractmethod
    def process(self, context: AgentContext) -> AgentResult:
        """
        Process the input and return result
        
        Args:
            context: Agent context with component and previous results
            
        Returns:
            AgentResult with output and status
        """
        pass
    
    def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute agent with error handling and retries
        
        Args:
            context: Agent context
            
        Returns:
            AgentResult
        """
        self.execution_count += 1
        start_time = datetime.now()
        
        max_retries = self.agent_config.get('max_retries', 3)
        retry_delay = self.agent_config.get('retry_delay', 1)
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                self.logger.info(
                    f"Executing {self.agent_name} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                
                result = self.process(context)
                
                execution_time = (datetime.now() - start_time).total_seconds()
                result.execution_time = execution_time
                self.total_execution_time += execution_time
                
                if result.is_success():
                    self.success_count += 1
                    self.logger.info(
                        f"{self.agent_name} completed successfully "
                        f"in {execution_time:.2f}s"
                    )
                    return result
                else:
                    self.logger.warning(
                        f"{self.agent_name} returned failure status: {result.error}"
                    )
                    last_error = result.error
                    
            except Exception as e:
                self.logger.error(f"{self.agent_name} execution error: {e}", exc_info=True)
                last_error = str(e)
                
                if attempt < max_retries - 1:
                    import time
                    self.logger.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
        
        # All retries failed
        self.failure_count += 1
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return AgentResult(
            agent_name=self.agent_name,
            status=AgentStatus.FAILED,
            output=None,
            error=last_error or "Max retries exceeded",
            execution_time=execution_time
        )
    
    def generate_with_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using LLM
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        try:
            response = self.llm_client.generate_for_agent(
                agent_name=self.agent_name,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content
        except Exception as e:
            self.logger.error(f"LLM generation error: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get agent execution statistics"""
        success_rate = (
            self.success_count / max(self.execution_count, 1)
        ) * 100
        
        avg_execution_time = (
            self.total_execution_time / max(self.execution_count, 1)
        )
        
        return {
            'agent_name': self.agent_name,
            'total_executions': self.execution_count,
            'successes': self.success_count,
            'failures': self.failure_count,
            'success_rate': round(success_rate, 2),
            'total_time': round(self.total_execution_time, 2),
            'average_time': round(avg_execution_time, 2)
        }
    
    def validate_input(self, context: AgentContext) -> bool:
        """
        Validate input context
        
        Args:
            context: Agent context
            
        Returns:
            True if valid, False otherwise
        """
        if not context.component:
            self.logger.error("No component in context")
            return False
        
        return True
    
    def create_system_prompt(self) -> str:
        """Create system prompt for this agent"""
        return f"You are a {self.agent_name} agent in a documentation generation system."
    
    def add_to_memory(self, role: str, content: str) -> None:
        """
        Add a message to the conversation memory.
        
        Args:
            role: The role of the message sender ('system', 'user', or 'assistant')
            content: The message content
        """
        self.memory.append({"role": role, "content": content})
        self.logger.debug(f"Added {role} message to memory ({len(content)} chars)")
    
    def clear_memory(self) -> None:
        """Clear the conversation memory."""
        self.memory = []
        self.logger.debug("Memory cleared")
    
    def generate_response(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response using the current conversation memory.
        
        Uses the messages stored via add_to_memory() to create a conversational
        context for the LLM.
        
        Args:
            temperature: Sampling temperature (default from config)
            max_tokens: Maximum tokens to generate (default from config)
            
        Returns:
            str: The generated response content
        """
        if not self.memory:
            raise ValueError("No messages in memory. Use add_to_memory() first.")
        
        try:
            response = self.llm_client.generate_with_messages(
                agent_name=self.agent_name,
                messages=self.memory,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content
        except Exception as e:
            self.logger.error(f"LLM generation error: {e}")
            raise