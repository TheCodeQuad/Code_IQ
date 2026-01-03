"""
LLM Client using llm.yaml config with Rate Limiting
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
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000
    model: Optional[str] = None

@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, int]
    latency: float
    metadata: Dict[str, Any]

class RateLimiter:
    """Simple token bucket rate limiter"""
    
    def __init__(self, max_requests_per_minute: int = 50):
        self.max_requests_per_minute = max_requests_per_minute
        self.interval = 60.0 / max_requests_per_minute
        self.last_request_time = 0
        self.logger = get_logger(__name__)
    
    def wait(self):
        """Wait if necessary to respect rate limit"""
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.interval:
            wait_time = self.interval - elapsed
            self.logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()

class LLMClient:
    """LLM Client using llm.yaml config with Rate Limiting"""

    def __init__(self):
        self.config = get_config()
        self.llm_config = self.config.get('llm', {})
        self.providers = self.llm_config.get('providers', {})
        self.agent_models = self.llm_config.get('agent_models', {})
        self.default_provider = next((k for k, v in self.providers.items() if v.get('enabled')), 'openrouter')
        self.default_model = self.providers[self.default_provider]['models']['default']
        self.base_url = self.providers[self.default_provider].get('api_base_url', "https://openrouter.ai/api/v1/chat/completions")
        self.api_key_env = self.providers[self.default_provider].get('api_key_env', None)
        if not self.api_key_env or self.api_key_env == "DUMMY":
            self.api_key = None
        else:
            self.api_key = os.getenv(self.api_key_env)
            if not self.api_key:
                raise ValueError(f"{self.api_key_env} not found in environment variables")
        
        # Initialize rate limiter
        rate_limit_config = self.providers[self.default_provider].get('rate_limits', {})
        max_requests = rate_limit_config.get('tier_1', {}).get('requests', 50)
        self.rate_limiter = RateLimiter(max_requests_per_minute=max_requests)
        
        # Stats tracking
        self.request_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        
        logger.info(f"LLM Client initialized with provider: {self.default_provider}, model: {self.default_model}")
        logger.info(f"Rate limiter: {max_requests} requests per minute")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response from LLM with rate limiting and retry logic"""
        max_retries = 4
        base_backoff = 2  # seconds

        for attempt in range(max_retries):
            self.rate_limiter.wait()
            start_time = time.time()
            model = request.model or self.default_model
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/your-repo",
                "X-Title": "Documentation Generator"
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
                content = data['choices'][0]['message']['content']
                usage = data.get('usage', {})
                latency = time.time() - start_time
                self.request_count += 1
                self.total_tokens += usage.get('total_tokens', 0)
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
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"LLM API request failed: {e}")
                raise
            except RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Request failed. Retrying in {wait_time}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
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
        """Generate response for specific agent with rate limiting"""
        agent_config = self.agent_models.get(agent_name, {})
        provider = agent_config.get('provider', self.default_provider)
        model = agent_config.get('model', self.default_model)
        params = agent_config.get('params', {})
        
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
        pricing = {
            'anthropic/claude-3.5-sonnet': {'input': 0.003, 'output': 0.015},
            'anthropic/claude-3-opus': {'input': 0.015, 'output': 0.075},
            'anthropic/claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            'openai/gpt-4-turbo': {'input': 0.01, 'output': 0.03},
            'openai/gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
            'mistralai/mistral-7b-instruct:free': {'input': 0.0, 'output': 0.0},
            'alibaba/tongyi-deepresearch-30b-a3b:free': {'input': 0.0, 'output': 0.0}
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