"""
LLM Client using OpenRouter
"""
import os
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import time
from backend.utils.logger import get_logger
from backend.utils.config_handler import get_config

logger = get_logger(__name__)

@dataclass
class LLMRequest:
    """LLM request data"""
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000
    model: Optional[str] = None

@dataclass
class LLMResponse:
    """LLM response data"""
    content: str
    model: str
    usage: Dict[str, int]
    latency: float
    metadata: Dict[str, Any]

class LLMClient:
    """OpenRouter LLM Client"""
    
    def __init__(self):
        self.config = get_config()
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.default_model = self.config.get('llm.default_model', 'anthropic/claude-3.5-sonnet')
        
        # Stats tracking
        self.request_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        
        logger.info(f"LLM Client initialized with model: {self.default_model}")
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response from LLM"""
        start_time = time.time()
        
        model = request.model or self.default_model
        
        # Build messages
        messages = []
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": request.prompt
        })
        
        # Prepare request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-repo",  # Optional
            "X-Title": "Documentation Generator"  # Optional
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract response
            content = data['choices'][0]['message']['content']
            usage = data.get('usage', {})
            
            latency = time.time() - start_time
            
            # Track usage
            self.request_count += 1
            self.total_tokens += usage.get('total_tokens', 0)
            
            # Calculate cost (approximate)
            cost = self._calculate_cost(model, usage)
            self.total_cost += cost
            
            logger.info(
                f"LLM Request #{self.request_count}: "
                f"Model={model}, "
                f"Tokens={usage.get('total_tokens', 0)}, "
                f"Cost=${cost:.4f}, "
                f"Latency={latency:.2f}s"
            )
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                latency=latency,
                metadata={'request_id': data.get('id')}
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise
    
    def generate_for_agent(
        self,
        agent_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response for specific agent"""
        # Get agent-specific configuration
        agent_config = self.config.get(f'agents.agent_models.{agent_name}', {})
        
        model = agent_config.get('model', self.default_model)
        params = agent_config.get('params', {})
        
        # Override with kwargs
        temperature = kwargs.get('temperature', params.get('temperature', 0.7))
        max_tokens = kwargs.get('max_tokens', params.get('max_tokens', 4000))
        
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model
        )
        
        return self.generate(request)
    
    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate approximate cost"""
        # OpenRouter pricing (approximate, check their docs for exact rates)
        pricing = {
            'anthropic/claude-3.5-sonnet': {
                'input': 0.003,
                'output': 0.015
            },
            'anthropic/claude-3-opus': {
                'input': 0.015,
                'output': 0.075
            },
            'anthropic/claude-3-haiku': {
                'input': 0.00025,
                'output': 0.00125
            },
            'openai/gpt-4-turbo': {
                'input': 0.01,
                'output': 0.03
            },
            'openai/gpt-3.5-turbo': {
                'input': 0.0005,
                'output': 0.0015
            }
        }
        
        rates = pricing.get(model, {'input': 0.001, 'output': 0.002})
        
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)
        
        cost = (input_tokens / 1000 * rates['input']) + (output_tokens / 1000 * rates['output'])
        return cost
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            'total_requests': self.request_count,
            'total_tokens': self.total_tokens,
            'total_cost': round(self.total_cost, 4),
            'average_tokens_per_request': round(self.total_tokens / max(self.request_count, 1), 2)
        }

# Singleton instance
_llm_client = None

def get_llm_client() -> LLMClient:
    """Get LLM client singleton"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
