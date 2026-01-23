"""Java language adapter for component extraction and dependency resolution"""
from ...treesitter.parser_factory import get_ts_parser
from .extractor import extract_components
from ...core.api_extractor import extract_api_endpoints


class JavaAdapter:
    """Adapter for Java language"""
    language = "java"
    extensions = [".java"]

    def __init__(self):
        self.parser = get_ts_parser("java")

    def parse(self, source):
        """Parse Java source code"""
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, tree, source, file_path, module_path):
        """Extract all code components including API endpoints"""
        # Extract regular components
        components = extract_components(tree, source, file_path, module_path)
        
        # Extract API endpoints (Spring, etc.)
        file_imports = self._extract_imports(tree)
        api_endpoints = extract_api_endpoints(
            source, file_path, module_path, self.language, file_imports
        )
        components.update(api_endpoints)
        
        return components

    def resolve_dependencies(self, component, tree, source, all_components):
        """Resolve dependencies for a component (not implemented for Java)"""
        return set()
    
    def _extract_imports(self, tree):
        """Extract imports from AST tree - consistent tree-based approach"""
        imports = []
        root = tree.root_node
        
        def walk(node):
            # Handle: import package.Class;
            if node.type == "import_declaration":
                import_node = None
                for child in node.children:
                    # Skip 'import' keyword and ';'
                    if child.type == "identifier" or (hasattr(child, 'type') and 'name' in child.type):
                        import_node = child
                    elif child.type == "scoped_identifier":
                        import_node = child
                    elif child.type == "dotted_name":
                        import_node = child
                
                if import_node:
                    import_text = import_node.text.decode()
                    imports.append(import_text)
                else:
                    # Fallback: extract the full import path
                    import_text = node.text.decode()
                    import_text = import_text.replace("import", "").replace(";", "").strip()
                    if import_text and not import_text.startswith("static"):
                        imports.append(import_text)
            
            for c in node.children:
                walk(c)
        
        walk(root)
        return imports

