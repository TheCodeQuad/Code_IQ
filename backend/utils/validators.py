# """
# Validation utilities
# """
# from typing import Any, Dict, List, Optional
# from pathlib import Path
# import re

# class Validator:
#     """Validation utilities"""
    
#     @staticmethod
#     def validate_file_path(file_path: str) -> bool:
#         """Validate file path exists"""
#         return Path(file_path).exists()
    
#     @staticmethod
#     def validate_directory(directory: str) -> bool:
#         """Validate directory exists"""
#         path = Path(directory)
#         return path.exists() and path.is_dir()
    
#     @staticmethod
#     def validate_language(language: str) -> bool:
#         """Validate programming language is supported"""
#         supported = ['python', 'javascript', 'typescript', 'java']
#         return language.lower() in supported
    
#     @staticmethod
#     def validate_component_id(component_id: str) -> bool:
#         """Validate component ID format"""
#         # Format: file_path:component_name
#         pattern = r'^[^:]+:[^:]+$'
#         return bool(re.match(pattern, component_id))
    
#     @staticmethod
#     def validate_score(score: float) -> bool:
#         """Validate score is between 0 and 100"""
#         return 0 <= score <= 100
    
#     @staticmethod
#     def validate_config(config: Dict[str, Any], required_keys: List[str]) -> bool:
#         """Validate configuration has required keys"""
#         return all(key in config for key in required_keys)
    
#     @staticmethod
#     def sanitize_filename(filename: str) -> str:
#         """Sanitize filename to remove invalid characters"""
#         # Remove invalid characters
#         filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
#         # Remove leading/trailing spaces and dots
#         filename = filename.strip('. ')
#         return filename
    
#     @staticmethod
#     def validate_docstring_style(style: str) -> bool:
#         """Validate docstring style"""
#         valid_styles = ['google', 'numpy', 'sphinx', 'restructuredtext']
#         return style.lower() in valid_styles


