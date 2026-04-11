"""
LLM Client with support for:
- Local inference via llama-cpp-python (no HTTP overhead)
- Remote API providers (OpenRouter, OpenAI, etc.)
"""
import os
import hashlib
import json
import requests
from requests.exceptions import RequestException
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
import time
from functools import lru_cache
from pathlib import Path
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


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        pass
    
    @abstractmethod
    def generate_for_agent(self, agent_name: str, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        pass
    
    @abstractmethod
    def generate_with_messages(
        self,
        agent_name: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate response using a list of conversation messages.
        
        Args:
            agent_name: Name of the calling agent
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLMResponse with generated content
        """
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
    
    def __init__(self, model_path: str, n_ctx: int = 8192, n_gpu_layers: int = -1, n_threads: int = None, main_gpu: int = 0):
        """
        Initialize with model loaded into memory.
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_gpu_layers: GPU layers (-1 for all, 0 for CPU only)
            n_threads: Number of CPU threads (None for auto)
            main_gpu: GPU device index to use (0 = first GPU, 1 = second, etc.)
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
        
        # Force CUDA to only see the target GPU before any CUDA initialization
        # This is required because llama-cpp-python ignores main_gpu on WDDM vs TCC setups
        os.environ["CUDA_VISIBLE_DEVICES"] = str(main_gpu)
        logger.info(f"Set CUDA_VISIBLE_DEVICES={main_gpu} to force model onto GPU {main_gpu}")
        
        # Check if CUDA is available (optional - llama-cpp-python handles it)
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if cuda_available:
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                logger.info(f"CUDA GPU detected: {gpu_name} ({gpu_memory:.2f} GB)")
            else:
                logger.warning("CUDA not detected - model may run on CPU")
        except (ImportError, OSError) as e:
            logger.debug(f"PyTorch GPU detection skipped: {e}")
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
            verbose=False
        )
        logger.info(f"Model loaded on GPU {main_gpu}")
        
        load_time = time.time() - start
        logger.info(f"Model loaded successfully in {load_time:.2f}s")
        logger.info(f"Context size: {n_ctx}, GPU layers: {n_gpu_layers} (-1 = all layers on GPU)")
        
        # Log actual GPU usage after loading
        try:
            # Try to get metadata about how model was loaded
            # This is model-specific but we can at least log the config used
            if n_gpu_layers == -1:
                logger.info("GPU layer configuration: Using ALL layers on GPU (maximum acceleration)")
            elif n_gpu_layers > 0:
                logger.info(f"GPU layer configuration: Using {n_gpu_layers} layers on GPU")
            else:
                logger.warning("GPU layer configuration: CPU only (no GPU acceleration)")
                logger.warning("⚠ To use GPU, set n_gpu_layers=-1 in config/llm.yaml")
        except Exception as e:
            logger.debug(f"Could not verify GPU layer info: {e}")
        
        self.model_path = model_path
        self.model_name = os.path.basename(model_path)
        self.config = get_config()

        # Cache settings (shared with rest of system via config/system.yaml)
        self._cache_enabled = self.config.get('system.cache.enabled', True)
        self._cache_ttl_s = int(self.config.get('system.cache.ttl', 86400) or 86400)
        self._cache_hits = 0
        self._mem_cache: Dict[str, Dict[str, Any]] = {}

        cache_dir_cfg = self.config.get('system.cache.directory', '.cache/') or '.cache/'
        project_root = Path(__file__).resolve().parents[2]
        cache_dir_path = Path(cache_dir_cfg)
        if not cache_dir_path.is_absolute():
            cache_dir_path = (project_root / cache_dir_path)
        self._cache_dir = (cache_dir_path / 'llm' / 'local').resolve()
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create cache directory {self._cache_dir}: {e}")
            self._cache_enabled = False

        self.request_count = 0
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def _cache_key_for_prompt(self, request: LLMRequest) -> str:
        payload = {
            'kind': 'prompt',
            'model_name': self.model_name,
            'model_path': self.model_path,
            'system_prompt': request.system_prompt or '',
            'prompt': request.prompt,
            'temperature': float(request.temperature),
            'max_tokens': int(request.max_tokens),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(blob).hexdigest()

    def _cache_key_for_messages(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        payload = {
            'kind': 'messages',
            'model_name': self.model_name,
            'model_path': self.model_path,
            'messages': messages,
            'temperature': float(temperature),
            'max_tokens': int(max_tokens),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(blob).hexdigest()

    def _cache_path(self, key: str) -> Path:
        # Avoid huge single directories
        return self._cache_dir / key[:2] / f"{key}.json"

    def _cache_get(self, key: str) -> Optional[LLMResponse]:
        if not self._cache_enabled:
            return None

        now = time.time()

        mem = self._mem_cache.get(key)
        if mem is not None:
            if now - float(mem.get('created_at', 0)) <= self._cache_ttl_s:
                self._cache_hits += 1
                return LLMResponse(
                    content=mem.get('content', ''),
                    model=mem.get('model', self.model_name),
                    usage=mem.get('usage', {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}),
                    latency=0.0,
                    metadata={**mem.get('metadata', {}), 'cached': True, 'cache': 'memory'}
                )
            self._mem_cache.pop(key, None)

        path = self._cache_path(key)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            created_at = float(data.get('created_at', 0))
            if now - created_at > self._cache_ttl_s:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                return None

            self._cache_hits += 1
            # Populate memory cache for this run
            self._mem_cache[key] = data
            return LLMResponse(
                content=data.get('content', ''),
                model=data.get('model', self.model_name),
                usage=data.get('usage', {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}),
                latency=0.0,
                metadata={**data.get('metadata', {}), 'cached': True, 'cache': 'disk'}
            )
        except Exception as e:
            logger.debug(f"Failed to read cache entry {path}: {e}")
            return None

    def _cache_put(self, key: str, response: LLMResponse) -> None:
        if not self._cache_enabled:
            return

        data = {
            'created_at': time.time(),
            'content': response.content,
            'model': response.model,
            'usage': response.usage,
            'metadata': response.metadata,
        }

        # Memory cache
        self._mem_cache[key] = data

        # Disk cache
        path = self._cache_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            os.replace(tmp, path)
        except Exception as e:
            logger.debug(f"Failed to write cache entry {path}: {e}")
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response via direct inference - no HTTP overhead"""
        cache_key = self._cache_key_for_prompt(request)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        return self._generate_and_cache(request)

    def _generate_and_cache(self, request: LLMRequest) -> LLMResponse:
        """Internal helper to generate and persist cache."""
        start_time = time.time()

        if request.system_prompt:
            full_prompt = f"<|im_start|>system\n{request.system_prompt}<|im_end|>\n<|im_start|>user\n{request.prompt}<|im_end|>\n<|im_start|>assistant\n"
        else:
            full_prompt = f"<|im_start|>user\n{request.prompt}<|im_end|>\n<|im_start|>assistant\n"

        output = self.llm(
            full_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stop=["<|im_end|>", "<|im_start|>"],
            echo=False
        )

        content = output['choices'][0]['text'].strip()
        usage = output.get('usage', {})
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

        response = LLMResponse(
            content=content,
            model=self.model_name,
            usage=normalized_usage,
            latency=latency,
            metadata={'local': True}
        )
        self._cache_put(self._cache_key_for_prompt(request), response)
        return response
    
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
    
    def generate_with_messages(
        self,
        agent_name: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate response using conversation messages (memory-based approach).
        
        Args:
            agent_name: Name of the calling agent
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (default 0.7)
            max_tokens: Maximum tokens to generate (default 4000)
            
        Returns:
            LLMResponse with generated content
        """
        temp = temperature or 0.7
        max_tok = max_tokens or 4000

        cache_key = self._cache_key_for_messages(messages, temp, max_tok)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        start_time = time.time()
        
        # Build prompt with chat template from messages
        full_prompt = ""
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            full_prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        full_prompt += "<|im_start|>assistant\n"
        
        # Direct inference
        output = self.llm(
            full_prompt,
            max_tokens=max_tok,
            temperature=temp,
            stop=["<|im_end|>", "<|im_start|>"],
            echo=False
        )
        
        content = output['choices'][0]['text'].strip()
        usage = output.get('usage', {})
        
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
            f"Local LLM (memory) Request #{self.request_count} for {agent_name}: "
            f"Messages={len(messages)}, Tokens={total_tokens}, Latency={latency:.2f}s"
        )
        
        response = LLMResponse(
            content=content,
            model=self.model_name,
            usage=normalized_usage,
            latency=latency,
            metadata={'local': True, 'memory_based': True}
        )

        self._cache_put(cache_key, response)
        return response
    
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


class RemoteAPIClient(BaseLLMClient):
    """Remote API Client for OpenRouter, OpenAI, etc."""

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
        
        # Response cache for repeated prompts (reduces redundant LLM calls)
        self._response_cache: Dict[str, LLMResponse] = {}
        self._cache_enabled = self.config.get('system.cache.enabled', True)
        self._cache_max_size = 100  # Max cached responses
        self._cache_hits = 0
        
        # Stats tracking
        self.request_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        
        logger.info(f"Remote API Client initialized with provider: {self.default_provider}, model: {self.default_model}")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response from remote API with rate limiting and retry logic"""
        max_retries = 4
        base_backoff = 2

        for attempt in range(max_retries):
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
                if hasattr(e, 'response') and e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Remote API request failed: {e}")
                raise
            except RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Request failed. Retrying in {wait_time}s...")
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

    def generate_with_messages(
        self,
        agent_name: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate response using conversation messages (memory-based approach).
        
        Args:
            agent_name: Name of the calling agent
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLMResponse with generated content
        """
        agent_config = self.agent_models.get(agent_name, {})
        params = agent_config.get('params', {})
        model = agent_config.get('model', self.default_model)
        
        temp = temperature if temperature is not None else params.get('temperature', 0.7)
        max_tok = max_tokens if max_tokens is not None else params.get('max_tokens', 4000)
        
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Build payload with messages directly (OpenAI/OpenRouter compatible)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tok
        }
        
        max_retries = 4
        base_backoff = 2
        
        for attempt in range(max_retries):
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
                    f"Remote API (memory) Request #{self.request_count} for {agent_name}: "
                    f"Messages={len(messages)}, Tokens={usage.get('total_tokens', 0)}, "
                    f"Cost=${cost:.4f}, Latency={latency:.2f}s"
                )
                
                return LLMResponse(
                    content=content,
                    model=model,
                    usage=usage,
                    latency=latency,
                    metadata={'request_id': data.get('id'), 'local': False, 'memory_based': True}
                )
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Remote API request failed: {e}")
                raise
            except RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = base_backoff * (2 ** attempt)
                    logger.warning(f"Request failed. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"Remote API request failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Remote API generation error: {e}")
                raise

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
            'mistralai/mistral-7b-instruct:free': {'input': 0.0, 'output': 0.0},
            'tngtech/deepseek-r1t-chimera:free': {'input': 0.0, 'output': 0.0},
            'alibaba/tongyi-deepresearch-30b-a3b:free': {'input': 0.0, 'output': 0.0}
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
            'model': self.default_model
        }
    
    def clear_cache(self):
        """Clear the response cache"""
        self._response_cache.clear()
        logger.info("LLM response cache cleared")


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
        llm_config = config.get_config('llm')  # Use get_config() to get the full llm dict
        providers = llm_config.get('providers', {}) if llm_config else {}
        local_config = providers.get('local', {})
        
        logger.debug(f"LLM config loaded: {bool(llm_config)}, local enabled: {local_config.get('enabled', False)}")
        
        # Check if local provider is enabled
        if local_config.get('enabled', False):
            mode = local_config.get('mode', 'llama_cpp')
            
            if mode == 'llama_cpp':
                # Use direct llama-cpp-python inference
                model_path = local_config.get('model_path', 'C:\\PROJECTS\\Code_IQ\\models\\qwen2.5-coder-1.5b-instruct-q4_k_m.gguf')
                
                # Convert relative paths to absolute
                model_path = str(Path(model_path).resolve())
                
                n_ctx = local_config.get('n_ctx', 8192)
                n_gpu_layers = local_config.get('n_gpu_layers', -1)
                n_threads = local_config.get('n_threads', None)
                main_gpu = local_config.get('main_gpu', 0)
                
                logger.info(f"Initializing LocalLlamaClient for direct inference...")
                logger.info(f"Model path resolved to: {model_path}")
                logger.info(f"Target GPU: {main_gpu}")
                try:
                    _llm_client = LocalLlamaClient(
                        model_path=model_path,
                        n_ctx=n_ctx,
                        n_gpu_layers=n_gpu_layers,
                        n_threads=n_threads,
                        main_gpu=main_gpu
                    )
                except ImportError as e:
                    logger.warning(
                        "llama-cpp-python is not installed. Falling back to RemoteAPIClient "
                        "(local HTTP/Ollama if configured)."
                    )
                    logger.warning(str(e))
                    _llm_client = RemoteAPIClient()
                except Exception as e:
                    logger.warning(f"LocalLlamaClient initialization failed: {e}")
                    if n_gpu_layers != 0:
                        logger.info("Retrying LocalLlamaClient in CPU mode (n_gpu_layers=0)...")
                        try:
                            _llm_client = LocalLlamaClient(
                                model_path=model_path,
                                n_ctx=n_ctx,
                                n_gpu_layers=0,
                                n_threads=n_threads,
                                main_gpu=main_gpu
                            )
                        except Exception as cpu_err:
                            logger.warning(
                                f"CPU LocalLlamaClient initialization failed: {cpu_err}. "
                                "Falling back to RemoteAPIClient (local HTTP/Ollama if configured)."
                            )
                            _llm_client = RemoteAPIClient()
                    else:
                        logger.warning(
                            "Local llama-cpp is already configured for CPU and still failed. "
                            "Falling back to RemoteAPIClient (local HTTP/Ollama if configured)."
                        )
                        _llm_client = RemoteAPIClient()
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