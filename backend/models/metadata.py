# """
# Metadata Models
# """
# from dataclasses import dataclass, field
# from typing import Dict, List, Optional, Any
# from datetime import datetime

# @dataclass
# class FileMetadata:
#     """Metadata about a source file"""
#     file_path: str
#     language: str
#     lines_of_code: int
#     num_functions: int
#     num_classes: int
#     num_imports: int
#     last_modified: Optional[datetime] = None
#     encoding: str = "utf-8"
#     metadata: Dict[str, Any] = field(default_factory=dict)

# @dataclass
# class ComponentMetadata:
#     """Additional metadata for a code component"""
#     author: Optional[str] = None
#     created_at: Optional[datetime] = None
#     last_modified: Optional[datetime] = None
#     version: Optional[str] = None
#     deprecated: bool = False
#     experimental: bool = False
#     private: bool = False
#     tags: List[str] = field(default_factory=list)
#     annotations: Dict[str, Any] = field(default_factory=dict)

# @dataclass
# class Metadata:
#     """General metadata container"""
#     project_name: str = ""
#     version: str = "1.0.0"
#     language: str = "python"
#     total_files: int = 0
#     total_components: int = 0
#     total_dependencies: int = 0
#     cycles_detected: int = 0
#     cycles_broken: int = 0
#     processing_time: float = 0.0
#     timestamp: datetime = field(default_factory=datetime.now)
#     config: Dict[str, Any] = field(default_factory=dict)
#     statistics: Dict[str, Any] = field(default_factory=dict)
    
#     def to_dict(self) -> Dict[str, Any]:
#         """Convert to dictionary"""
#         return {
#             'project_name': self.project_name,
#             'version': self.version,
#             'language': self.language,
#             'total_files': self.total_files,
#             'total_components': self.total_components,
#             'total_dependencies': self.total_dependencies,
#             'cycles_detected': self.cycles_detected,
#             'cycles_broken': self.cycles_broken,
#             'processing_time': self.processing_time,
#             'timestamp': self.timestamp.isoformat(),
#             'config': self.config,
#             'statistics': self.statistics,
#         }