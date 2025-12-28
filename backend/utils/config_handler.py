"""
Configuration handler
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

class ConfigHandler:
    """Handles all configuration loading and management"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_dir: str = "config"):
        if self._initialized:
            return
            
        self.config_dir = Path(config_dir)
        self._configs = {}
        self._load_env()
        self._load_all_configs()
        self._initialized = True
    
    def _load_env(self):
        """Load environment variables"""
        load_dotenv()
    
    def _load_all_configs(self):
        """Load all YAML configuration files"""
        config_files = [
            'system.yaml',
            'navigator.yaml',
            'agents.yaml',
            'evaluator.yaml',
            'api.yaml',
            'llm.yaml',
            'templates.yaml'
        ]
        
        for config_file in config_files:
            config_path = self.config_dir / config_file
            if config_path.exists():
                config_name = config_file.replace('.yaml', '')
                self._configs[config_name] = self._load_yaml(config_path)
    
    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load a YAML file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading config {file_path}: {e}")
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Example:
            config.get('system.pipeline.stages')
            config.get('api.default_provider')
        """
        keys = key.split('.')
        
        # First key is the config file name
        if not keys:
            return default
        
        config_name = keys[0]
        if config_name not in self._configs:
            return default
        
        value = self._configs[config_name]
        
        # Navigate through nested keys
        for k in keys[1:]:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_env(self, key: str, default: Any = None) -> Any:
        """Get environment variable"""
        return os.getenv(key, default)
    
    def get_config(self, config_name: str) -> Dict[str, Any]:
        """Get entire configuration file"""
        return self._configs.get(config_name, {})
    
    def reload(self):
        """Reload all configurations"""
        self._configs = {}
        self._load_env()
        self._load_all_configs()

# Singleton instance
_config_handler = None

def get_config() -> ConfigHandler:
    """Get configuration handler singleton"""
    global _config_handler
    if _config_handler is None:
        _config_handler = ConfigHandler()
    return _config_handler