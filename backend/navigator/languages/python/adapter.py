"""Python language adapter for component extraction and dependency resolution"""
from ...treesitter.parser_factory import get_ts_parser
from .extractor import extract_components, resolve_dependencies  # ← Import both
from ...core.api_extractor import extract_api_endpoints


class PythonAdapter:
    """Adapter for Python language"""
    language = "python"
    extensions = [".py"]

    def __init__(self):
        self.parser = get_ts_parser("python")

    def parse(self, source):
        """Parse Python source code"""
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, tree, source, file_path, module_path):
        """Extract all code components including API endpoints"""
        # Extract regular components WITH RICH METADATA
        components = extract_components(tree, source, file_path, module_path)
        
        # Extract API endpoints
        file_imports = self._extract_imports(tree)
        api_endpoints = extract_api_endpoints(
            source, file_path, module_path, self.language, file_imports
        )
        components.update(api_endpoints)
        
        return components

    def resolve_dependencies(self, component, tree, source, all_components):
        """Resolve dependencies for a component"""
        return resolve_dependencies(component, tree, source, all_components)
    
    def _extract_imports(self, tree):
        """Extract imports from tree"""
        imports = []
        root = tree.root_node
        
        def walk(node):
            if node.type == "import_statement":
                for child in node.children:
                    if child.type in ("dotted_name", "aliased_import"):
                        imports.append(child.text.decode())
            
            elif node.type == "import_from_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        imports.append(child.text.decode())
            
            for c in node.children:
                walk(c)
        
        walk(root)
        return imports

