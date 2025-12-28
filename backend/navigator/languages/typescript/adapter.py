from treesitter.parser_factory import get_ts_parser
from languages.javascript.extractor import extract_components
from languages.javascript.dependencies import resolve_dependencies

class TypeScriptAdapter:
    language = "typescript"
    extensions = [".ts",".tsx"]

    def __init__(self):
        self.parser = get_ts_parser("typescript")

    def parse(self, source):
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, *args):
        return extract_components(*args)

    def resolve_dependencies(self, *args):
        return resolve_dependencies(*args)
