"""
Intermediate Representation for code components.
Matches the structure from the AST-based parser.
"""

from dataclasses import dataclass, field
from typing import Set, Optional, Any, Dict


@dataclass
class CodeComponent:
    """
    Represents a single code component in a codebase.
    
    Supported types:
    - 'class': Class definition
    - 'function': Top-level function
    - 'method': Class method
    - 'global_variable': Module-level variable/constant (GUI widgets, configs, etc.)
    
    Compatible with AST-based parser output.
    """
    # Unique identifier for the component, format: module_path.ClassName.method_name
    id: str
    
    # Programming language of this component
    language: str
    
    # Type of component: 'class', 'function', 'method', or 'global_variable'
    type: str
    
    # Full path to the file containing this component
    file_path: str
    
    # Module path (e.g., "package.submodule")
    module_path: str
    
    # Set of component IDs this component depends on
    depends_on: Set[str] = field(default_factory=set)
    
    # Original source code of the component
    source_code: Optional[str] = None
    
    # Line numbers in the file (1-indexed)
    start_line: int = 0
    end_line: int = 0
    
    # Whether the component already has a docstring
    has_docstring: bool = False
    
    # Content of the docstring if it exists, empty string otherwise
    docstring: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this component to a dictionary representation for JSON serialization.
        
        Returns:
            dict: Serializable representation of the component
        """
        return {
            'id': self.id,
            'language': self.language,
            'type': self.type,
            'file_path': self.file_path,
            'module_path': self.module_path,
            'depends_on': list(self.depends_on),
            'start_line': self.start_line,
            'end_line': self.end_line,
            'has_docstring': self.has_docstring,
            'docstring': self.docstring,
            'source_code': self.source_code[:500] + "..." if self.source_code and len(self.source_code) > 500 else self.source_code,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CodeComponent':
        """
        Create a CodeComponent from a dictionary representation.
        
        Args:
            data: Dictionary containing component data
            
        Returns:
            CodeComponent: Reconstructed component object
        """
        component = CodeComponent(
            id=data['id'],
            language=data.get('language', 'python'),
            type=data['type'],
            file_path=data['file_path'],
            module_path=data.get('module_path', ''),
            depends_on=set(data.get('depends_on', [])),
            source_code=data.get('source_code'),
            start_line=data.get('start_line', 0),
            end_line=data.get('end_line', 0),
            has_docstring=data.get('has_docstring', False),
            docstring=data.get('docstring', "")
        )
        return component

    def __repr__(self) -> str:
        """String representation for debugging"""
        deps_preview = list(self.depends_on)[:3]
        deps_str = f"{len(self.depends_on)} deps" if len(self.depends_on) > 3 else str(deps_preview)
        return f"CodeComponent(id={self.id}, type={self.type}, depends_on={deps_str})"

    def __hash__(self) -> int:
        """Make component hashable by its ID"""
        return hash(self.id)

    def __eq__(self, other) -> bool:
        """Components are equal if they have the same ID"""
        if not isinstance(other, CodeComponent):
            return False
        return self.id == other.id
    
    def is_global_variable(self) -> bool:
        """Check if this component is a global variable"""
        return self.type == "global_variable"
    
    def is_function(self) -> bool:
        """Check if this component is a function"""
        return self.type == "function"
    
    def is_method(self) -> bool:
        """Check if this component is a method"""
        return self.type == "method"
    
    def is_class(self) -> bool:
        """Check if this component is a class"""
        return self.type == "class"