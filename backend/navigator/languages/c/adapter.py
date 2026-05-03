# languages/c/adapter.py

"""
C Language Adapter for Navigator

Integrates C parsing, extraction, and dependency resolution
into the DocAgent pipeline using tree-sitter.

Supports:
  - .c source files
  - .h header files
"""

from ...treesitter.parser_factory import get_ts_parser
from .extractor import extract_components
from .dependencies import resolve_dependencies


class CAdapter:
    """
    Adapter for C language support in DocAgent.

    Provides:
    - Tree-sitter parsing for C
    - Component extraction (functions, structs, enums, typedefs, macros)
    - Dependency resolution (#include, function calls, type usage)

    Matches existing adapter architecture with centralized parser factory.
    """

    language = "c"
    extensions = [".c", ".h"]

    def __init__(self):
        """Initialize C parser using centralized parser factory."""
        self.parser = get_ts_parser("c")

    def parse(self, source):
        """
        Parse C source code into AST.

        Args:
            source: C source code as string

        Returns:
            tree-sitter Tree object
        """
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, tree, source, file_path, module_path):
        """
        Extract all components from C source.

        Args:
            tree:        tree-sitter Tree object
            source:      Source code string
            file_path:   Absolute path to the source file
            module_path: Dot-separated module path

        Returns:
            Dictionary mapping component_id -> CodeComponent
        """
        return extract_components(tree, source, file_path, module_path)

    def resolve_dependencies(self, component, tree, source, all_components):
        """
        Resolve dependencies for a C component.

        Args:
            component:      CodeComponent to resolve dependencies for
            tree:           tree-sitter Tree object
            source:         Source code string
            all_components: Dictionary of all components in the project

        Returns:
            Set of component IDs that this component depends on
        """
        return resolve_dependencies(component, tree, source, all_components)
