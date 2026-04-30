from ...treesitter.parser_factory import get_ts_parser
from .extractor import extract_components, extract_components_ast
from .dependencies import resolve_dependencies
import ast

class PythonAdapter:
    language = "python"
    extensions = [".py"]

    def __init__(self):
        # Initialize tree-sitter parser; fall back to Python AST if unavailable
        try:
            self.parser = get_ts_parser("python")
            self.use_ast = False
        except Exception:
            self.parser = None
            self.use_ast = True

    def parse(self, source):
        if self.use_ast or self.parser is None:
            # Return Python AST Module when tree-sitter is unavailable
            return ast.parse(source)
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, tree, source, file_path, module_path):
        if self.use_ast or not hasattr(tree, "root_node"):
            return extract_components_ast(tree, source, file_path, module_path)
        return extract_components(tree, source, file_path, module_path)

    def resolve_dependencies(self, component, tree, source, all_components):
        return resolve_dependencies(component, tree, source, all_components)
