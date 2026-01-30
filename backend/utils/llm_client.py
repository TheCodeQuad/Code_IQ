"""
LLM Client with support for:
- Local inference via llama-cpp-python (no HTTP overhead)
- Remote API providers (OpenRouter, OpenAI, etc.)
"""
import os
import requests
from requests.exceptions import RequestException
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
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


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        pass
    
    @abstractmethod
    def generate_for_agent(self, agent_name: str, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        pass


class LocalLlamaClient(BaseLLMClient):
    """
    Local LLM Client using llama-cpp-python.
    Model is loaded ONCE at initialization and kept in memory.
    No HTTP overhead, no rate limiting needed.
    """
    
    def __init__(self, model_path: str, n_ctx: int = 8192, n_gpu_layers: int = -1, n_threads: int = None):
        """
        Initialize with model loaded into memory.
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_gpu_layers: GPU layers (-1 for all, 0 for CPU only)
            n_threads: Number of CPU threads (None for auto)
        """
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. Install with:\n"
                "  pip install llama-cpp-python\n"
                "For GPU support:\n"
                "  CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install llama-cpp-python --force-reinstall --no-cache-dir"
            )
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        logger.info(f"Loading local model from {model_path}...")
        start = time.time()
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
            verbose=False
        )
        
        load_time = time.time() - start
        logger.info(f"Model loaded successfully in {load_time:.2f}s")
        logger.info(f"Context size: {n_ctx}, GPU layers: {n_gpu_layers}")
        
        self.model_path = model_path
        self.model_name = os.path.basename(model_path)
        self.request_count = 0
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response via direct inference - no HTTP overhead"""
        start_time = time.time()
        
        # Build prompt with chat template
        if request.system_prompt:
            full_prompt = f"<|im_start|>system\n{request.system_prompt}<|im_end|>\n<|im_start|>user\n{request.prompt}<|im_end|>\n<|im_start|>assistant\n"
        else:
            full_prompt = f"<|im_start|>user\n{request.prompt}<|im_end|>\n<|im_start|>assistant\n"
        
        # Direct inference - no HTTP, no rate limiting!
        output = self.llm(
            full_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stop=["<|im_end|>", "<|im_start|>"],
            echo=False
        )
        
        content = output['choices'][0]['text'].strip()
        usage = output.get('usage', {})
        
        # Normalize usage keys
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = prompt_tokens + completion_tokens
        
        normalized_usage = {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens
        }
        
        latency = time.time() - start_time
        
        self.request_count += 1
        self.total_tokens += total_tokens
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        
        logger.info(
            f"Local LLM Request #{self.request_count}: "
            f"Tokens={total_tokens} (in={prompt_tokens}, out={completion_tokens}), "
            f"Latency={latency:.2f}s"
        )
        
        return LLMResponse(
            content=content,
            model=self.model_name,
            usage=normalized_usage,
            latency=latency,
            metadata={'local': True}
        )
    
    def generate_for_agent(
        self,
        agent_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response for specific agent"""
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 4000)
        )
        return self.generate(request)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            'total_requests': self.request_count,
            'total_tokens': self.total_tokens,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_cost': 0.0,  # Local inference is free!
            'average_tokens_per_request': round(self.total_tokens / max(self.request_count, 1), 2),
            'model': self.model_name,
            'provider': 'local'
        }


class RateLimiter:
    """Simple token bucket rate limiter for remote API calls"""
    
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


class RemoteAPIClient(BaseLLMClient):
    """Remote API Client for OpenRouter, OpenAI, etc. with Rate Limiting"""

    def __init__(self):
        self.config = get_config()
        self.llm_config = self.config.get('llm', {})
        self.providers = self.llm_config.get('providers', {})
        self.agent_models = self.llm_config.get('agent_models', {})
        
        # Find enabled remote provider (skip 'local' provider)
        self.default_provider = next(
            (k for k, v in self.providers.items() if v.get('enabled') and k != 'local'),
            'openrouter'
        )
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
        
        logger.info(f"Remote API Client initialized with provider: {self.default_provider}, model: {self.default_model}")
        logger.info(f"Rate limiter: {max_requests} requests per minute")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response from remote API with rate limiting and retry logic"""
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
                    f"Remote API Request #{self.request_count}: "
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
                    metadata={'request_id': data.get('id'), 'local': False}
                )
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Remote API request failed: {e}")
                raise
            except RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Request failed. Retrying in {wait_time}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Remote API request failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Remote API generation error: {e}")
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
            'tngtech/deepseek-r1t-chimera:free': {'input': 0.0, 'output': 0.0},
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
            'average_tokens_per_request': round(self.total_tokens / max(self.request_count, 1), 2),
            'provider': self.default_provider,
            'model': self.default_model
        }


# Backward compatibility alias
LLMClient = RemoteAPIClient


# Singleton instance
_llm_client: Optional[BaseLLMClient] = None

def get_llm_client() -> BaseLLMClient:
    """
    Get LLM client singleton.
    
    Returns LocalLlamaClient if local provider is enabled,
    otherwise returns RemoteAPIClient.
    """
    global _llm_client
    if _llm_client is None:
        config = get_config()
        llm_config = config.get('llm', {})
        providers = llm_config.get('providers', {})
        local_config = providers.get('local', {})
        
        # Check if local provider is enabled
        if local_config.get('enabled', False):
            mode = local_config.get('mode', 'llama_cpp')
            
            if mode == 'llama_cpp':
                # Use direct llama-cpp-python inference
                model_path = local_config.get('model_path', 'models/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf')
                n_ctx = local_config.get('n_ctx', 8192)
                n_gpu_layers = local_config.get('n_gpu_layers', -1)
                n_threads = local_config.get('n_threads', None)
                
                logger.info("Initializing LocalLlamaClient for direct inference...")
                _llm_client = LocalLlamaClient(
                    model_path=model_path,
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    n_threads=n_threads
                )
            else:
                # Fallback to Ollama HTTP API (mode == 'ollama')
                logger.info("Initializing RemoteAPIClient for Ollama...")
                _llm_client = RemoteAPIClient()
        else:
            # Use remote API provider
            logger.info("Initializing RemoteAPIClient for remote API...")
            _llm_client = RemoteAPIClient()
    
    return _llm_client


def reset_llm_client():
    """Reset the LLM client singleton (useful for testing or switching providers)"""
    global _llm_client
    _llm_client = None
    logger.info("LLM client reset")