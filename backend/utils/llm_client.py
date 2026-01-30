"""
LLM Client using llm.yaml config with Rate Limiting and Response Caching
Supports: OpenRouter, Ollama (local), and other OpenAI-compatible APIs
"""
import os
import hashlib
import requests
from requests.exceptions import RequestException
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import time
from functools import lru_cache
from backend.utils.logger import get_logger
from backend.utils.config_handler import get_config
import psutil

logger = get_logger(__name__)

@dataclass
class LLMRequest:
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000
    model: Optional[str] = None
    # Ollama-specific options
    num_ctx: Optional[int] = None
    num_batch: Optional[int] = None
    num_gpu: Optional[int] = None
    num_parallel: Optional[int] = None  # ADD
    num_thread: Optional[int] = None  # ADD THIS LINE

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
    """LLM Client using llm.yaml config with Rate Limiting and Response Caching"""

    def __init__(self):
        self.config = get_config()
        self.llm_config = self.config.get('llm', {})
        self.providers = self.llm_config.get('providers', {})
        self.agent_models = self.llm_config.get('agent_models', {})
        self.default_provider = next((k for k, v in self.providers.items() if v.get('enabled')), 'openrouter')
        self.default_model = self.providers[self.default_provider]['models']['default']
        self.base_url = self.providers[self.default_provider].get('api_base_url', "https://openrouter.ai/api/v1/chat/completions")
        self.api_key_env = self.providers[self.default_provider].get('api_key_env', None)
        
        # Get provider-specific config
        self.provider_config = self.providers.get(self.default_provider, {})
        self.default_params = self.provider_config.get('default_params', {})
        self.gpu_config = self.provider_config.get('gpu_config', {})
        
        # AUTO-DETECT CPU CORES
        cpu_count = os.cpu_count() or 16
        if 'num_thread' not in self.default_params:
            self.default_params['num_thread'] = cpu_count
        
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
        
        # Response cache for repeated prompts (reduces redundant LLM calls)
        self._response_cache: Dict[str, LLMResponse] = {}
        self._cache_enabled = self.config.get('system.cache.enabled', True)
        self._cache_max_size = 100  # Max cached responses
        self._cache_hits = 0
        
        # Stats tracking
        self.request_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        
        logger.info(f"LLM Client initialized with provider: {self.default_provider}, model: {self.default_model}")
        logger.info(f"CPU cores detected: {cpu_count}, using {self.default_params.get('num_thread')} threads")
        logger.info(f"GPU config: num_gpu={self.default_params.get('num_gpu')}, num_batch={self.default_params.get('num_batch')}")

    def _get_cache_key(self, prompt: str, system_prompt: str, model: str, temperature: float) -> str:
        """Generate a cache key from request parameters"""
        key_data = f"{prompt}|{system_prompt}|{model}|{temperature}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[LLMResponse]:
        """Get cached response if available"""
        if self._cache_enabled and cache_key in self._response_cache:
            self._cache_hits += 1
            logger.debug(f"Cache hit (total: {self._cache_hits})")
            return self._response_cache[cache_key]
        return None

    def _cache_response(self, cache_key: str, response: LLMResponse):
        """Cache a response for future use"""
        if not self._cache_enabled:
            return
        # Simple LRU: remove oldest if at capacity
        if len(self._response_cache) >= self._cache_max_size:
            oldest_key = next(iter(self._response_cache))
            del self._response_cache[oldest_key]
        self._response_cache[cache_key] = response

    def _is_ollama_provider(self, provider: str = None) -> bool:
        """Check if using local Ollama provider"""
        provider = provider or self.default_provider
        return provider == "local" or "localhost:11434" in self.base_url

    def _generate_ollama(self, request: LLMRequest, agent_params: Dict = None) -> LLMResponse:
        """Generate response using Ollama's native API with FULL GPU utilization"""
        start_time = time.time()
        model = request.model or self.default_model
        
        # Merge params: default < agent-specific < request
        params = {**self.default_params}
        if agent_params:
            params.update(agent_params)
        
        # Build Ollama options for GPU optimization
        options = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
            "num_ctx": request.num_ctx or params.get('num_ctx', 8192),
            "num_batch": request.num_batch or params.get('num_batch', 512),
            "num_gpu": request.num_gpu or params.get('num_gpu', -1),
            "num_thread": request.num_thread or params.get('num_thread', os.cpu_count() or 16),  # FIX: Use request.num_thread
            "num_parallel": request.num_parallel or params.get('num_parallel', 2),
        }
        
        # Use Ollama chat endpoint
        url = f"{self.base_url}/api/chat"
        
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        
        try:
            logger.debug(
                f"Ollama request: model={model}, "
                f"num_gpu={options['num_gpu']}, "
                f"num_ctx={options['num_ctx']}, "
                f"num_batch={options['num_batch']}, "
                f"num_thread={options['num_thread']}, "
                f"num_parallel={options['num_parallel']}"
            )
            
            response = requests.post(
                url,
                json=payload,
                timeout=self.provider_config.get('timeout', 300)
            )
            response.raise_for_status()
            data = response.json()
            
            content = data.get('message', {}).get('content', '')
            
            # Ollama returns eval_count and prompt_eval_count
            usage = {
                'prompt_tokens': data.get('prompt_eval_count', 0),
                'completion_tokens': data.get('eval_count', 0),
                'total_tokens': data.get('prompt_eval_count', 0) + data.get('eval_count', 0)
            }
            
            latency = time.time() - start_time
            self.request_count += 1
            self.total_tokens += usage.get('total_tokens', 0)
            
            # Log GPU stats
            eval_duration = data.get('eval_duration', 0) / 1e9
            tokens_per_sec = data.get('eval_count', 0) / eval_duration if eval_duration > 0 else 0
            
            logger.info(
                f"Ollama Request #{self.request_count}: "
                f"Model={model}, "
                f"Tokens={usage.get('total_tokens', 0)}, "
                f"Speed={tokens_per_sec:.1f} tok/s, "
                f"Latency={latency:.2f}s, "
                f"GPU_Layers={options['num_gpu']}, "  # ADD
                f"Batch_Size={options['num_batch']}, "  # ADD
                f"Context={options['num_ctx']}"  # ADD
            )
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                latency=latency,
                metadata={
                    'eval_duration': eval_duration,
                    'tokens_per_second': tokens_per_sec,
                    'load_duration': data.get('load_duration', 0) / 1e9,
                    'gpu_layers_offloaded': options['num_gpu'],  # ADD
                    'batch_size': options['num_batch'],  # ADD
                    'context_window': options['num_ctx'],  # ADD
                    'parallel_requests': options['num_parallel'],  # ADD
                }
            )
            
        except RequestException as e:
            logger.error(f"Ollama API request failed: {e}")
            raise

    def _generate_openai_compatible(self, request: LLMRequest) -> LLMResponse:
        """Generate response using OpenAI-compatible API (OpenRouter, etc.)"""
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

    def generate(self, request: LLMRequest, agent_params: Dict = None) -> LLMResponse:
        """Generate response from LLM with rate limiting, caching, and retry logic"""
        
        # Check cache first (only for deterministic requests with low temperature)
        if request.temperature <= 0.3:
            cache_key = self._get_cache_key(
                request.prompt,
                request.system_prompt or "",
                request.model or self.default_model,
                request.temperature
            )
            cached = self._get_cached_response(cache_key)
            if cached:
                return cached
        else:
            cache_key = None
        
        max_retries = 4
        base_backoff = 2

        for attempt in range(max_retries):
            self.rate_limiter.wait()
            
            try:
                # Route to appropriate provider
                if self._is_ollama_provider():
                    response = self._generate_ollama(request, agent_params)
                else:
                    response = self._generate_openai_compatible(request)
                
                # Cache the response for future use
                if cache_key:
                    self._cache_response(cache_key, response)
                
                return response
                    
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"LLM API request failed: {e}")
                raise
            except RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Request failed. Retrying in {wait_time}s...")
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
        """Generate response for specific agent"""
        agent_config = self.agent_models.get(agent_name, {})
        params = agent_config.get('params', {})
        model = agent_config.get('model', self.default_model)
        
        temperature = kwargs.get('temperature', params.get('temperature', 0.7))
        max_tokens = kwargs.get('max_tokens', params.get('max_tokens', 4000))
        
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            num_ctx=params.get('num_ctx'),
            num_batch=params.get('num_batch'),
            num_gpu=params.get('num_gpu'),
            num_parallel=params.get('num_parallel'),  # ADD
            num_thread=params.get('num_thread'),
        )
        
        return self.generate(request, agent_params=params)

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate approximate cost (0 for local models)"""
        if self._is_ollama_provider():
            return 0.0
            
        pricing = {
            'anthropic/claude-3.5-sonnet': {'input': 0.003, 'output': 0.015},
            'anthropic/claude-3-opus': {'input': 0.015, 'output': 0.075},
            'anthropic/claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            'openai/gpt-4-turbo': {'input': 0.01, 'output': 0.03},
            'openai/gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
            'qwen2.5:7b': {'input': 0.0, 'output': 0.0},  # Local = free
            'tngtech/deepseek-r1t-chimera:free': {'input': 0.0, 'output': 0.0},  # OpenRouter free tier
        }
        
        rates = pricing.get(model, {'input': 0.001, 'output': 0.002})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)
        return (input_tokens / 1000 * rates['input']) + (output_tokens / 1000 * rates['output'])

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics including cache performance"""
        return {
            'total_requests': self.request_count,
            'total_tokens': self.total_tokens,
            'total_cost': round(self.total_cost, 4),
            'average_tokens_per_request': round(self.total_tokens / max(self.request_count, 1), 2),
            'provider': self.default_provider,
            'model': self.default_model,
            'cache_hits': self._cache_hits,
            'cache_size': len(self._response_cache),
            'cache_hit_rate': round(self._cache_hits / max(self.request_count + self._cache_hits, 1) * 100, 1),
        }
    
    def clear_cache(self):
        """Clear the response cache"""
        self._response_cache.clear()
        logger.info("LLM response cache cleared")

# Singleton instance
_llm_client = None

def get_llm_client() -> LLMClient:
    """Get LLM client singleton"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client