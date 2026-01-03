"""
File handling utilities
"""
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import shutil
from datetime import datetime

class FileHandler:
    """Handles file I/O operations"""
    
    @staticmethod
    def read_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
        """Read text file"""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except Exception as e:
            raise IOError(f"Error reading file {file_path}: {e}")
    
    @staticmethod
    def write_file(
        file_path: Union[str, Path],
        content: str,
        encoding: str = 'utf-8',
        create_dirs: bool = True
    ):
        """Write text file"""
        file_path = Path(file_path)
        
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
        except Exception as e:
            raise IOError(f"Error writing file {file_path}: {e}")
    
    @staticmethod
    def read_json(file_path: Union[str, Path]) -> Dict[str, Any]:
        """Read JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise IOError(f"Error reading JSON file {file_path}: {e}")
    
    @staticmethod
    def write_json(
        file_path: Union[str, Path],
        data: Any,
        indent: int = 2,
        create_dirs: bool = True
    ):
        """Write JSON file"""
        file_path = Path(file_path)
        
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
        except Exception as e:
            raise IOError(f"Error writing JSON file {file_path}: {e}")

    @staticmethod
    def read_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
        """Read YAML file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise IOError(f"Error reading YAML file {file_path}: {e}")

    @staticmethod
    def write_yaml(
        file_path: Union[str, Path],
        data: Any,
        create_dirs: bool = True
    ):
        """Write YAML file"""
        file_path = Path(file_path)
        
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            raise IOError(f"Error writing YAML file {file_path}: {e}")

    @staticmethod
    def list_files(
        directory: Union[str, Path],
        pattern: str = "*",
        recursive: bool = False
    ) -> List[Path]:
        """List files in directory"""
        directory = Path(directory)
        
        if not directory.exists():
            return []
        
        if recursive:
            return list(directory.rglob(pattern))
        else:
            return list(directory.glob(pattern))

    @staticmethod
    def copy_file(source: Union[str, Path], destination: Union[str, Path]):
        """Copy file"""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    @staticmethod
    def move_file(source: Union[str, Path], destination: Union[str, Path]):
        """Move file"""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    @staticmethod
    def delete_file(file_path: Union[str, Path]):
        """Delete file"""
        Path(file_path).unlink(missing_ok=True)

    @staticmethod
    def create_backup(file_path: Union[str, Path], backup_dir: Optional[str] = None) -> Path:
        """Create backup of file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if backup_dir:
            backup_path = Path(backup_dir)
        else:
            backup_path = file_path.parent / "backups"
        
        backup_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"{file_path.stem}_{timestamp}{file_path.suffix}"
        
        shutil.copy2(file_path, backup_file)
        return backup_file

    @staticmethod
    def ensure_dir(directory: Union[str, Path]):
        """Ensure directory exists"""
        Path(directory).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def serialize_component(comp):
        """Serialize a component (or any object) to JSON-serializable format"""
        from dataclasses import is_dataclass, asdict
        from enum import Enum
        
        def serialize_value(val):
            """Recursively serialize a value"""
            # Handle None
            if val is None:
                return None
            
            # Handle enums
            if isinstance(val, Enum):
                return val.value
            
            # Handle dataclasses (like Location, Parameter)
            if is_dataclass(val) and not isinstance(val, type):
                try:
                    return {k: serialize_value(v) for k, v in asdict(val).items()}
                except TypeError:
                    return str(val)
            
            # Handle dictionaries
            if isinstance(val, dict):
                return {k: serialize_value(v) for k, v in val.items()}
            
            # Handle lists and tuples
            if isinstance(val, (list, tuple)):
                return [serialize_value(item) for item in val]
            
            # Handle sets
            if isinstance(val, set):
                return list(val)
            
            # Handle primitive types
            if isinstance(val, (str, int, float, bool)):
                return val
            
            # Fallback: try __dict__
            if hasattr(val, '__dict__'):
                try:
                    return {k: serialize_value(v) for k, v in val.__dict__.items()}
                except (TypeError, AttributeError):
                    return str(val)
            
            # Last resort: convert to string
            return str(val)
        
        # Start serialization
        if is_dataclass(comp) and not isinstance(comp, type):
            return {k: serialize_value(v) for k, v in asdict(comp).items()}
        else:
            d = comp.__dict__.copy()
            return {k: serialize_value(v) for k, v in d.items()}
