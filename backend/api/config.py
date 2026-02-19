# """
# API Configuration Loader
# """
# import os
# import yaml
# from pathlib import Path
# from typing import Dict, Any, Optional
# from dotenv import load_dotenv

# class APIConfig:
#     """Manages API configuration"""
    
#     def __init__(self, config_dir: str = "config"):
#         self.config_dir = Path(config_dir)
#         self.load_environment()
#         self.api_config = self.load_yaml("api_config.yaml")
#         self.llm_providers = self.load_yaml("llm_providers.yaml")
        
#     def load_environment(self):
#         """Load environment variables from .env"""
#         load_dotenv()
        
#     def load_yaml(self, filename: str) -> Dict[str, Any]:
#         """Load YAML configuration file"""
#         config_path = self.config_dir / filename
#         with open(config_path, 'r') as f:
#             return yaml.safe_load(f)
    
#     def get_provider_config(self, provider: str) -> Dict[str, Any]:
#         """Get configuration for specific provider"""
#         return self.llm_providers['providers'].get(provider, {})
    
#     def get_api_key(self, provider: str) -> str:
#         """Get API key from environment"""
#         key_map = {
#             'anthropic': 'ANTHROPIC_API_KEY',
#             'openai': 'OPENAI_API_KEY',
#             'custom': 'CUSTOM_API_KEY'
#         }
        
#         env_key = key_map.get(provider)
#         if not env_key:
#             raise ValueError(f"Unknown provider: {provider}")
        
#         api_key = os.getenv(env_key)
#         if not api_key:
#             raise ValueError(f"API key not found for {provider}. Set {env_key} in .env")
        
#         return api_key
    
#     def get_model_config(self, provider: str, model_name: Optional[str] = None) -> Dict[str, Any]:
#         """Get model configuration"""
#         provider_config = self.get_provider_config(provider)
        
#         if not model_name:
#             model_name = provider_config['models']['default']
        
#         return provider_config['models'].get(model_name, {})
    
#     def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
#         """Get LLM configuration for specific agent"""
#         return self.llm_providers['agent_models'].get(agent_name, {})
    
#     def get_rate_limits(self, provider: str) -> Dict[str, Any]:
#         """Get rate limit configuration"""
#         provider_config = self.get_provider_config(provider)
#         tier = os.getenv(f"{provider.upper()}_API_TIER", "tier_1")
#         return provider_config.get('rate_limits', {}).get(tier, {})
    
#     def get_cost_config(self) -> Dict[str, Any]:
#         """Get cost tracking configuration"""
#         return {
#             'enabled': self.api_config['api']['cost_tracking']['enabled'],
#             'warn_threshold': float(os.getenv('COST_WARN_THRESHOLD', 10.0)),
#             'hard_limit': float(os.getenv('COST_HARD_LIMIT', 100.0)),
#             'alert_email': os.getenv('COST_ALERT_EMAIL')
#         }

# # Singleton instance
# _config_instance = None

# def get_api_config() -> APIConfig:
#     """Get or create API configuration singleton"""
#     global _config_instance
#     if _config_instance is None:
#         _config_instance = APIConfig()
#     return _config_instance