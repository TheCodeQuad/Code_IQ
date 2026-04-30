# languages/java/adapter.py

"""
Java Language Adapter for Navigator

Integrates Java parsing, extraction, and dependency resolution
into the DocAgent pipeline.
"""

from ...treesitter.parser_factory import get_ts_parser
from .extractor import extract_components
from .dependencies import resolve_dependencies


class JavaAdapter:
    """
    Adapter for Java language support in DocAgent.
    
    Provides:
    - Tree-sitter parsing for Java
    - Component extraction (classes, methods, fields, constructors)
    - Dependency resolution
    
    Matches existing adapter architecture with centralized parser factory.
    """
    
    language = "java"
    extensions = [".java"]

    def __init__(self):
        """Initialize Java parser using centralized parser factory"""
        self.parser = get_ts_parser("java")

    def parse(self, source):
        """
        Parse Java source code into AST.
        
        Args:
            source: Java source code as string
            
        Returns:
            tree-sitter Tree object
        """
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, *args):
        """
        Extract all components from Java source.
        
        Args:
            *args: (tree, source, file_path, module_path)
            
        Returns:
            Dictionary mapping component_id -> CodeComponent
        """
        return extract_components(*args)

    def resolve_dependencies(self, component, tree, source, all_components):
        """
        Resolve dependencies for a Java component.
        
        Args:
            component: CodeComponent to resolve dependencies for
            tree: tree-sitter Tree object
            source: Source code string
            all_components: Dictionary of all components in the project
            
        Returns:
            Set of component IDs that this component depends on
        """
        return resolve_dependencies(component, tree, source, all_components)