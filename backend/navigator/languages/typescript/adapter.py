from ...treesitter.parser_factory import get_ts_parser
from .extractor import extract_components, extract_imports
from .dependencies import resolve_dependencies
from ...core.api_extractor import extract_api_endpoints

class TypeScriptAdapter:
    """Adapter for TypeScript language"""
    language = "typescript"
    extensions = [".ts", ".tsx"]

    def __init__(self):
        self.parser = get_ts_parser("typescript")
        try:
            self.tsx_parser = get_ts_parser("tsx")
        except Exception:
            # Fallback: if tsx grammar not available, reuse typescript parser
            self.tsx_parser = self.parser

    def parse(self, source, file_path=None):
        """Parse TypeScript source code. Uses tsx grammar for .tsx files."""
        parser = self.parser
        if file_path and file_path.endswith(".tsx"):
            parser = self.tsx_parser
        return parser.parse(bytes(source, "utf8"))

    def extract_components(self, tree, source, file_path, module_path):
        """Extract all code components including API endpoints"""
        # Extract regular components
        components = extract_components(tree, source, file_path, module_path)
        
        # Extract API endpoints (Express, NestJS, etc.)
        file_imports = extract_imports(tree)
        api_endpoints = extract_api_endpoints(
            source, file_path, module_path, self.language, file_imports
        )
        components.update(api_endpoints)
        
        return components

    def resolve_dependencies(self, component, tree, source, all_components):
        """Resolve dependencies for a component"""
        return resolve_dependencies(component, tree, source, all_components)

