from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient

PROVIDERS = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
}

__all__ = ["OpenAIClient", "AnthropicClient", "PROVIDERS"]
