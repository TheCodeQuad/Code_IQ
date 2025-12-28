"""
Code Component Models
Represents functions, classes, methods extracted by Navigator
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum

class ComponentType(Enum):
    """Type of code component"""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    MODULE = "module"
    IMPORT = "import"

@dataclass
class Location:
    """Source code location"""
    file_path: str
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0
    
    def __str__(self):
        return f"{self.file_path}:{self.start_line}-{self.end_line}"

@dataclass
class Parameter:
    """Function/method parameter"""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_required: bool = True
    description: Optional[str] = None

@dataclass
class CodeComponent:
    """Represents a code component (function, class, method, etc.)"""
    
    # Core identification
    id: str  # Unique identifier
    name: str
    type: ComponentType
    location: Location
    
    # Code content
    source_code: str
    signature: str  # e.g., "def my_function(x: int, y: str) -> bool:"
    
    # Structure
    parameters: List[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    
    # For classes
    parent_classes: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)  # Method IDs
    attributes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Documentation (if exists)
    existing_docstring: Optional[str] = None
    
    # Dependencies
    calls: List[str] = field(default_factory=list)  # Component IDs called
    imports: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # Dependency IDs
    
    # Metadata
    complexity: Optional[int] = None  # Cyclomatic complexity
    lines_of_code: int = 0
    language: str = "python"
    is_async: bool = False
    is_generator: bool = False
    is_abstract: bool = False
    is_static: bool = False
    is_class_method: bool = False
    
    # Topological ordering (from Navigator)
    priority: int = 0  # 0 = no dependencies, higher = more dependencies
    dependency_level: int = 0
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'location': {
                'file_path': self.location.file_path,
                'start_line': self.location.start_line,
                'end_line': self.location.end_line,
            },
            'source_code': self.source_code,
            'signature': self.signature,
            'parameters': [
                {
                    'name': p.name,
                    'type_hint': p.type_hint,
                    'default_value': p.default_value,
                    'is_required': p.is_required
                }
                for p in self.parameters
            ],
            'return_type': self.return_type,
            'decorators': self.decorators,
            'parent_classes': self.parent_classes,
            'methods': self.methods,
            'attributes': self.attributes,
            'existing_docstring': self.existing_docstring,
            'calls': self.calls,
            'imports': self.imports,
            'depends_on': self.depends_on,
            'complexity': self.complexity,
            'lines_of_code': self.lines_of_code,
            'language': self.language,
            'is_async': self.is_async,
            'is_generator': self.is_generator,
            'priority': self.priority,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeComponent':
        """Create from dictionary"""
        location = Location(
            file_path=data['location']['file_path'],
            start_line=data['location']['start_line'],
            end_line=data['location']['end_line'],
        )
        
        parameters = [
            Parameter(
                name=p['name'],
                type_hint=p.get('type_hint'),
                default_value=p.get('default_value'),
                is_required=p.get('is_required', True)
            )
            for p in data.get('parameters', [])
        ]
        
        return cls(
            id=data['id'],
            name=data['name'],
            type=ComponentType(data['type']),
            location=location,
            source_code=data['source_code'],
            signature=data['signature'],
            parameters=parameters,
            return_type=data.get('return_type'),
            decorators=data.get('decorators', []),
            parent_classes=data.get('parent_classes', []),
            methods=data.get('methods', []),
            attributes=data.get('attributes', []),
            existing_docstring=data.get('existing_docstring'),
            calls=data.get('calls', []),
            imports=data.get('imports', []),
            depends_on=data.get('depends_on', []),
            complexity=data.get('complexity'),
            lines_of_code=data.get('lines_of_code', 0),
            language=data.get('language', 'python'),
            is_async=data.get('is_async', False),
            is_generator=data.get('is_generator', False),
            priority=data.get('priority', 0),
            metadata=data.get('metadata', {}),
        )