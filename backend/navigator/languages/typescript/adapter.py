from ...treesitter.parser_factory import get_ts_parser
from .extractor import extract_components

class TypeScriptAdapter:
    language = "typescript"
    extensions = [".ts",".tsx"]

    def __init__(self):
        self.parser = get_ts_parser("typescript")

    def parse(self, source):
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, *args):
        return extract_components(*args)

    def resolve_dependencies(self, component, tree, source, all_components):
        # TypeScript extractor already sets depends_on during extraction
        # Return empty list to avoid overwriting
        return []

