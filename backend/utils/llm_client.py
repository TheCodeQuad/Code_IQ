"""
High-level LLM Client Interface
"""
from typing import Optional, Dict, Any
from backend.api.config import get_api_config
from backend.api.client import APIRequest, APIResponse
from backend.api.providers.anthropic_client import AnthropicClient
from backend.api.providers.openai_client import OpenAIClient
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    """High-level interface for LLM operations"""
    
    def __init__(self):
        self.config = get_api_config()
        self.clients = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize API clients for enabled providers"""
        for provider_name, provider_config in self.config.llm_providers['providers'].items():
            if provider_config.get('enabled', False):
                try:
                    api_key = self.config.get_api_key(provider_name)
                    
                    if provider_name == 'anthropic':
                        self.clients[provider_name] = AnthropicClient(api_key, provider_config)
                    elif provider_name == 'openai':
                        self.clients[provider_name] = OpenAIClient(api_key, provider_config)
                    
                    logger.info(f"Initialized {provider_name} client")
                except Exception as e:
                    logger.warning(f"Failed to initialize {provider_name} client: {e}")
    
    def generate_for_agent(
        self, 
        agent_name: str, 
        prompt: str,
        **kwargs
    ) -> APIResponse:
        """Generate response for specific agent"""
        agent_config = self.config.get_agent_config(agent_name)
        
        provider = agent_config.get('provider', self.config.api_config['api']['default_provider'])
        model = agent_config.get('model')
        params = agent_config.get('params', {})
        
        # Override with kwargs
        params.update(kwargs)
        
        request = APIRequest(
            prompt=prompt,
            model=model,
            temperature=params.get('temperature', 0.7),
            max_tokens=params.get('max_tokens', 4000),
            metadata={'agent': agent_name}
        )
        
        client = self.clients.get(provider)
        if not client:
            raise ValueError(f"Provider {provider} not initialized")
        
        return client.generate(request)
    
    def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> APIResponse:
        """Generate response with custom parameters"""
        if not provider:
            provider = self.config.api_config['api']['default_provider']
        
        client = self.clients.get(provider)
        if not client:
            raise ValueError(f"Provider {provider} not initialized")
        
        if not model:
            model = self.config.get_provider_config(provider)['models']['default']
        
        request = APIRequest(
            prompt=prompt,
            model=model,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 4000),
            metadata=kwargs.get('metadata', {})
        )
        
        return client.generate(request)

# Singleton instance
_llm_client = None

def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client