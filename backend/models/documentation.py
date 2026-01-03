"""
Documentation Models
Represents generated documentation
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class Example:
    """Code example"""
    description: str
    code: str
    output: Optional[str] = None
    
@dataclass
class DocSection:
    """A section of documentation"""
    title: str
    content: str
    examples: List[Example] = field(default_factory=list)
    subsections: List['DocSection'] = field(default_factory=list)

@dataclass
class Documentation:
    """Generated documentation for a code component"""
    
    # Component reference
    component_id: str
    component_name: str
    component_type: str
    
    # Main documentation
    summary: str  # One-line summary
    description: str  # Detailed description
    
    # Structured sections
    parameters_doc: List[Dict[str, str]] = field(default_factory=list)
    # [{"name": "x", "type": "int", "description": "..."}]
    
    returns_doc: Optional[Dict[str, str]] = None
    # {"type": "bool", "description": "..."}
    
    raises_doc: List[Dict[str, str]] = field(default_factory=list)
    # [{"exception": "ValueError", "description": "..."}]
    
    examples: List[Example] = field(default_factory=list)
    
    # Additional sections
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    see_also: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    
    # For classes
    attributes_doc: List[Dict[str, str]] = field(default_factory=list)
    methods_doc: List[str] = field(default_factory=list)  # Documentation IDs
    
    # Generated docstring (formatted)
    docstring: str = ""  # Google/NumPy/Sphinx format
    
    # Metadata
    style: str = "google"  # google, numpy, sphinx
    language: str = "en"
    generated_at: datetime = field(default_factory=datetime.now)
    generated_by: str = "multi-agent-system"
    version: str = "1.0.0"
    
    # Quality metrics
    completeness_score: float = 0.0
    clarity_score: float = 0.0
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'component_id': self.component_id,
            'component_name': self.component_name,
            'component_type': self.component_type,
            'summary': self.summary,
            'description': self.description,
            'parameters_doc': self.parameters_doc,
            'returns_doc': self.returns_doc,
            'raises_doc': self.raises_doc,
            'examples': [
                {
                    'description': ex.description,
                    'code': ex.code,
                    'output': ex.output
                }
                for ex in self.examples
            ],
            'notes': self.notes,
            'warnings': self.warnings,
            'see_also': self.see_also,
            'references': self.references,
            'attributes_doc': self.attributes_doc,
            'methods_doc': self.methods_doc,
            'docstring': self.docstring,
            'style': self.style,
            'language': self.language,
            'generated_at': self.generated_at.isoformat(),
            'generated_by': self.generated_by,
            'version': self.version,
            'completeness_score': self.completeness_score,
            'clarity_score': self.clarity_score,
            'metadata': self.metadata,
        }
    
    def format_docstring(self, style: Optional[str] = None) -> str:
        """Format documentation as docstring"""
        style = style or self.style
        
        if style == "google":
            return self._format_google()
        elif style == "numpy":
            return self._format_numpy()
        elif style == "sphinx":
            return self._format_sphinx()
        else:
            return self._format_google()
    
    def _format_google(self) -> str:
        """Format as Google-style docstring"""
        lines = [self.summary, ""]
        
        if self.description:
            lines.extend([self.description, ""])
        
        if self.parameters_doc:
            lines.append("Args:")
            for param in self.parameters_doc:
                type_str = f" ({param['type']})" if param.get('type') else ""
                lines.append(f"    {param['name']}{type_str}: {param['description']}")
            lines.append("")
        
        if self.returns_doc:
            lines.append("Returns:")
            type_str = f" ({self.returns_doc['type']})" if self.returns_doc.get('type') else ""
            lines.append(f"    {type_str}: {self.returns_doc['description']}")
            lines.append("")
        
        if self.raises_doc:
            lines.append("Raises:")
            for exc in self.raises_doc:
                lines.append(f"    {exc['exception']}: {exc['description']}")
            lines.append("")
        
        if self.examples:
            lines.append("Examples:")
            for ex in self.examples:
                lines.append(f"    {ex.description}")
                lines.append(f"    >>> {ex.code}")
                if ex.output:
                    lines.append(f"    {ex.output}")
            lines.append("")
        
        return "\n".join(lines).rstrip()
    
    def _format_numpy(self) -> str:
        """Format as NumPy-style docstring"""
        lines = [self.summary, ""]
        
        if self.description:
            lines.extend([self.description, ""])
        
        if self.parameters_doc:
            lines.append("Parameters")
            lines.append("----------")
            for param in self.parameters_doc:
                type_str = f" : {param['type']}" if param.get('type') else ""
                lines.append(f"{param['name']}{type_str}")
                lines.append(f"    {param['description']}")
            lines.append("")
        
        if self.returns_doc:
            lines.append("Returns")
            lines.append("-------")
            type_str = self.returns_doc.get('type', '')
            lines.append(type_str)
            lines.append(f"    {self.returns_doc['description']}")
            lines.append("")
        
        return "\n".join(lines).rstrip()
    
    def _format_sphinx(self) -> str:
        """Format as Sphinx-style docstring"""
        lines = [self.summary, ""]
        
        if self.description:
            lines.extend([self.description, ""])
        
        for param in self.parameters_doc:
            type_str = f" {param['type']}" if param.get('type') else ""
            lines.append(f":param{type_str} {param['name']}: {param['description']}")
        
        if self.returns_doc:
            type_str = f" {self.returns_doc['type']}" if self.returns_doc.get('type') else ""
            lines.append(f":return{type_str}: {self.returns_doc['description']}")
        
        return "\n".join(lines).rstrip()