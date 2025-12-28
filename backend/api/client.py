"""
Base API Client
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class APIRequest:
    """API request data"""
    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4000
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class APIResponse:
    """API response data"""
    content: str
    model: str
    usage: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency: float = 0.0

class BaseAPIClient(ABC):
    """Base class for all API clients"""
    
    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.api_key = api_key
        self.config = config
        self.request_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        
    @abstractmethod
    def generate(self, request: APIRequest) -> APIResponse:
        """Generate response from API"""
        pass
    
    @abstractmethod
    def generate_stream(self, request: APIRequest):
        """Generate streaming response from API"""
        pass
    
    def calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate cost based on token usage"""
        model_config = self.config['models'].get(
            usage.get('model'), 
            self.config['models']['default']
        )
        
        input_cost = (usage['input_tokens'] / 1000) * model_config.get('cost_per_1k_input', 0)
        output_cost = (usage['output_tokens'] / 1000) * model_config.get('cost_per_1k_output', 0)
        
        return input_cost + output_cost
    
    def track_usage(self, response: APIResponse):
        """Track API usage and costs"""
        self.request_count += 1
        self.total_tokens += response.usage.get('total_tokens', 0)
        cost = self.calculate_cost(response.usage)
        self.total_cost += cost
        
        logger.info(
            f"API Request #{self.request_count}: "
            f"Tokens={response.usage.get('total_tokens', 0)}, "
            f"Cost=${cost:.4f}, "
            f"Total Cost=${self.total_cost:.4f}"
        )